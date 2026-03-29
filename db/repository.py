"""GameRepository — single persistence layer for all game data."""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from db.converters import (
    game_event_to_row,
    knowledge_node_to_row,
    location_to_row,
    npc_to_row,
    player_to_row,
    row_to_game_event,
    row_to_knowledge_node,
    row_to_location,
)
from db.converters import (
    row_to_npc,
    row_to_player,
    row_to_scene,
    row_to_setting,
    scene_to_row,
    setting_to_row,
)
from knowledge.graph import KnowledgeGraph
from knowledge.node import EdgeType
from models.game_state import GameState
from timeline.event import GameEvent


class GameRepository:
    """Async repository for loading/saving game state to PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Session management ────────────────────────────────

    async def get_or_create_session(self, telegram_chat_id: int) -> dict:
        """Return session row dict, creating one if it doesn't exist."""
        stmt = (
            pg_insert(tbl.sessions)
            .values(
                id=str(_uuid.uuid4()),
                telegram_chat_id=telegram_chat_id,
            )
            .on_conflict_do_nothing(index_elements=["telegram_chat_id"])
        )
        await self._session.execute(stmt)

        query_result = await self._session.execute(
            select(tbl.sessions).where(tbl.sessions.c.telegram_chat_id == telegram_chat_id)
        )
        row = query_result.mappings().one()
        return dict(row)

    async def update_session(self, session_id: str, *, state: str | None = None, language: str | None = None) -> None:
        update_fields: dict[str, Any] = {}
        if state is not None:
            update_fields["state"] = state
        if language is not None:
            update_fields["language"] = language
        if update_fields:
            await self._session.execute(
                update(tbl.sessions).where(tbl.sessions.c.id == session_id).values(**update_fields)
            )

    # ── Full state load ───────────────────────────────────

    async def load_game_state(self, session_id: str) -> tuple[GameState, KnowledgeGraph, list[GameEvent]] | None:
        """Load full game state from PG. Returns None if no game exists for this session."""
        # Load game_states row
        gs_query = await self._session.execute(
            select(tbl.game_states).where(tbl.game_states.c.session_id == session_id)
        )
        gs_row = gs_query.mappings().first()
        if gs_row is None:
            return None
        gs_row = dict(gs_row)
        game_state_id = gs_row["id"]

        # Load setting
        setting_query = await self._session.execute(
            select(tbl.settings).where(tbl.settings.c.game_state_id == game_state_id)
        )
        setting_row = setting_query.mappings().first()
        if setting_row is None:
            return None
        setting = row_to_setting(dict(setting_row))

        # Load knowledge graph
        kg = KnowledgeGraph()
        nodes_query = await self._session.execute(
            select(tbl.knowledge_nodes).where(tbl.knowledge_nodes.c.game_state_id == game_state_id)
        )
        for row in nodes_query.mappings():
            node = row_to_knowledge_node(dict(row))
            kg.add_node(node)

        edges_query = await self._session.execute(
            select(tbl.knowledge_edges).where(tbl.knowledge_edges.c.game_state_id == game_state_id)
        )
        for row in edges_query.mappings():
            kg.add_edge(
                row["from_node_id"],
                row["to_node_id"],
                EdgeType(row["edge_type"]),
                row["metadata_"] if row["metadata_"] else None,
            )

        # Build GameState
        game_state = GameState(setting=setting, knowledge_graph=kg)
        game_state.uuid = gs_row["id"]
        game_state.turn_count = gs_row["turn_count"]
        game_state.scene_number = gs_row.get("scene_number", 0)
        game_state.game_clock = gs_row["game_clock"]
        game_state.game_time = gs_row["game_time"]
        game_state.conversation_log = gs_row["conversation_log"]
        game_state.scene_conversation_log = gs_row.get("scene_conversation_log", [])
        game_state.pending_clarification = gs_row.get("pending_clarification")

        # Load player
        player_query = await self._session.execute(
            select(tbl.players).where(tbl.players.c.game_state_id == game_state_id)
        )
        player_row = player_query.mappings().first()
        if player_row:
            game_state.player = row_to_player(dict(player_row))

        # Load locations
        locations_query = await self._session.execute(
            select(tbl.locations).where(tbl.locations.c.game_state_id == game_state_id)
        )
        for row in locations_query.mappings():
            loc = row_to_location(dict(row))
            game_state.locations[loc.uuid] = loc

        # Load NPCs
        npcs_query = await self._session.execute(select(tbl.npcs).where(tbl.npcs.c.game_state_id == game_state_id))
        for row in npcs_query.mappings():
            npc = row_to_npc(dict(row))
            game_state.npcs[npc.uuid] = npc

        # Load current scene
        scene_query = await self._session.execute(
            select(tbl.scenes).where(
                tbl.scenes.c.game_state_id == game_state_id,
                tbl.scenes.c.is_current == True,  # noqa: E712
            )
        )
        scene_row = scene_query.mappings().first()
        if scene_row:
            game_state.current_scene = row_to_scene(dict(scene_row))

        # Load events
        events_query = await self._session.execute(
            select(tbl.game_events).where(tbl.game_events.c.game_state_id == game_state_id)
        )
        events = [row_to_game_event(dict(event_row)) for event_row in events_query.mappings()]

        return game_state, kg, events

    # ── Full state save ───────────────────────────────────

    async def save_game_state(
        self,
        session_id: str,
        game_state: GameState,
        knowledge_graph: KnowledgeGraph,
        events: list[GameEvent],
    ) -> None:
        """Persist full game state to PG (upsert game_states, delete+insert children)."""
        # Upsert game_states row
        stmt = (
            pg_insert(tbl.game_states)
            .values(
                id=game_state.uuid,
                session_id=session_id,
                turn_count=game_state.turn_count,
                scene_number=game_state.scene_number,
                game_clock=game_state.game_clock,
                game_time=game_state.game_time,
                conversation_log=game_state.conversation_log,
                scene_conversation_log=game_state.scene_conversation_log,
                pending_clarification=game_state.pending_clarification,
            )
            .on_conflict_do_update(
                index_elements=["session_id"],
                set_={
                    "turn_count": game_state.turn_count,
                    "scene_number": game_state.scene_number,
                    "game_clock": game_state.game_clock,
                    "game_time": game_state.game_time,
                    "conversation_log": game_state.conversation_log,
                    "scene_conversation_log": game_state.scene_conversation_log,
                    "pending_clarification": game_state.pending_clarification,
                },
            )
            .returning(tbl.game_states.c.id)
        )
        upsert_result = await self._session.execute(stmt)
        game_state_id = upsert_result.scalar_one()
        await self._session.flush()

        # Setting (upsert)
        setting_row = setting_to_row(game_state.setting, game_state_id)
        stmt = (
            pg_insert(tbl.settings)
            .values(**setting_row)
            .on_conflict_do_update(
                index_elements=["game_state_id"],
                set_={key: col_val for key, col_val in setting_row.items() if key not in ("id", "game_state_id")},
            )
        )
        await self._session.execute(stmt)

        # Player (upsert)
        player_row = player_to_row(game_state.player, game_state_id)
        stmt = (
            pg_insert(tbl.players)
            .values(**player_row)
            .on_conflict_do_update(
                index_elements=["game_state_id"],
                set_={key: col_val for key, col_val in player_row.items() if key not in ("id", "game_state_id")},
            )
        )
        await self._session.execute(stmt)

        # Locations (delete + insert)
        await self._session.execute(delete(tbl.locations).where(tbl.locations.c.game_state_id == game_state_id))
        if game_state.locations:
            rows = [location_to_row(loc, game_state_id) for loc in game_state.locations.values()]
            await self._session.execute(tbl.locations.insert(), rows)

        # NPCs (delete + insert)
        await self._session.execute(delete(tbl.npcs).where(tbl.npcs.c.game_state_id == game_state_id))
        if game_state.npcs:
            rows = [npc_to_row(npc, game_state_id) for npc in game_state.npcs.values()]
            await self._session.execute(tbl.npcs.insert(), rows)

        # Scenes (delete + insert current)
        await self._session.execute(delete(tbl.scenes).where(tbl.scenes.c.game_state_id == game_state_id))
        if game_state.current_scene:
            row = scene_to_row(game_state.current_scene, game_state_id, is_current=True)
            await self._session.execute(tbl.scenes.insert().values(**row))

        # Knowledge nodes (delete + insert)
        await self._session.execute(
            delete(tbl.knowledge_nodes).where(tbl.knowledge_nodes.c.game_state_id == game_state_id)
        )
        nodes = knowledge_graph.all_nodes()
        if nodes:
            rows = [knowledge_node_to_row(node, game_state_id) for node in nodes]
            await self._session.execute(tbl.knowledge_nodes.insert(), rows)

        # Knowledge edges (delete + insert)
        await self._session.execute(
            delete(tbl.knowledge_edges).where(tbl.knowledge_edges.c.game_state_id == game_state_id)
        )
        edge_rows: list[dict] = []
        for node in nodes:
            for target_id, edge_type in knowledge_graph.get_edges_from(node.uuid):
                edge_rows.append(
                    {
                        "game_state_id": game_state_id,
                        "from_node_id": node.uuid,
                        "to_node_id": target_id,
                        "edge_type": edge_type.value,
                        "metadata_": {},
                    }
                )
        if edge_rows:
            await self._session.execute(tbl.knowledge_edges.insert(), edge_rows)

        # Events (delete + insert)
        await self._session.execute(delete(tbl.game_events).where(tbl.game_events.c.game_state_id == game_state_id))
        if events:
            rows = [game_event_to_row(ev, game_state_id) for ev in events]
            await self._session.execute(tbl.game_events.insert(), rows)

    # ── Admin queries ─────────────────────────────────────

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """List sessions with basic game info for admin view."""
        stmt = (
            select(
                tbl.sessions.c.id,
                tbl.sessions.c.telegram_chat_id,
                tbl.sessions.c.state,
                tbl.sessions.c.language,
                tbl.sessions.c.created_at,
                tbl.sessions.c.updated_at,
                tbl.game_states.c.turn_count,
                tbl.game_states.c.game_clock,
                tbl.game_states.c.game_time,
            )
            .outerjoin(tbl.game_states, tbl.game_states.c.session_id == tbl.sessions.c.id)
            .order_by(tbl.sessions.c.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        sessions_query = await self._session.execute(stmt)
        return [dict(row) for row in sessions_query.mappings()]

    async def get_session_detail(self, session_id: str) -> dict | None:
        """Get full session detail for admin view."""
        session_query = await self._session.execute(select(tbl.sessions).where(tbl.sessions.c.id == session_id))
        session_row = session_query.mappings().first()
        if not session_row:
            return None
        detail: dict[str, Any] = {"session": dict(session_row)}

        # Game state
        gs_query = await self._session.execute(
            select(tbl.game_states).where(tbl.game_states.c.session_id == session_id)
        )
        gs_row = gs_query.mappings().first()
        if not gs_row:
            detail["game_state"] = None
            return detail
        gs_row = dict(gs_row)
        game_state_id = gs_row["id"]
        detail["game_state"] = gs_row

        # Setting
        setting_query = await self._session.execute(
            select(tbl.settings).where(tbl.settings.c.game_state_id == game_state_id)
        )
        row = setting_query.mappings().first()
        detail["setting"] = dict(row) if row else None

        # Player
        player_query = await self._session.execute(
            select(tbl.players).where(tbl.players.c.game_state_id == game_state_id)
        )
        row = player_query.mappings().first()
        detail["player"] = dict(row) if row else None

        # Counts
        from sqlalchemy import func

        for table_name, table in (
            ("location_count", tbl.locations),
            ("npc_count", tbl.npcs),
            ("knowledge_node_count", tbl.knowledge_nodes),
            ("event_count", tbl.game_events),
        ):
            count_query = await self._session.execute(
                select(func.count()).select_from(table).where(table.c.game_state_id == game_state_id)
            )
            detail[table_name] = count_query.scalar()

        return detail

    async def get_conversation_log(self, session_id: str) -> list[dict]:
        """Get conversation log for a session."""
        log_query = await self._session.execute(
            select(tbl.game_states.c.conversation_log).where(tbl.game_states.c.session_id == session_id)
        )
        row = log_query.scalar()
        return row if row else []

    async def get_npcs(self, session_id: str) -> list[dict]:
        """Get all NPCs for a session."""
        npcs_query = await self._session.execute(
            select(tbl.npcs)
            .join(tbl.game_states, tbl.game_states.c.id == tbl.npcs.c.game_state_id)
            .where(tbl.game_states.c.session_id == session_id)
        )
        return [dict(row) for row in npcs_query.mappings()]

    async def get_locations(self, session_id: str) -> list[dict]:
        """Get all locations for a session."""
        locations_query = await self._session.execute(
            select(tbl.locations)
            .join(tbl.game_states, tbl.game_states.c.id == tbl.locations.c.game_state_id)
            .where(tbl.game_states.c.session_id == session_id)
        )
        return [dict(row) for row in locations_query.mappings()]

    async def get_knowledge_graph(self, session_id: str) -> dict:
        """Get knowledge graph nodes and edges for a session."""
        # Get game_state_id
        gs_id_query = await self._session.execute(
            select(tbl.game_states.c.id).where(tbl.game_states.c.session_id == session_id)
        )
        game_state_id = gs_id_query.scalar()
        if not game_state_id:
            return {"nodes": [], "edges": []}

        kg_nodes_query = await self._session.execute(
            select(tbl.knowledge_nodes).where(tbl.knowledge_nodes.c.game_state_id == game_state_id)
        )
        nodes = [dict(row) for row in kg_nodes_query.mappings()]

        kg_edges_query = await self._session.execute(
            select(tbl.knowledge_edges).where(tbl.knowledge_edges.c.game_state_id == game_state_id)
        )
        edges = [dict(row) for row in kg_edges_query.mappings()]

        return {"nodes": nodes, "edges": edges}

    async def get_events(self, session_id: str) -> list[dict]:
        """Get all events for a session."""
        events_query = await self._session.execute(
            select(tbl.game_events)
            .join(tbl.game_states, tbl.game_states.c.id == tbl.game_events.c.game_state_id)
            .where(tbl.game_states.c.session_id == session_id)
            .order_by(tbl.game_events.c.scheduled_at)
        )
        return [dict(row) for row in events_query.mappings()]

    # ── AI call logs ──────────────────────────────────────

    async def save_ai_call_logs(self, logs: list[dict[str, Any]], turn_number: int | None = None) -> None:
        """Batch insert AI call log entries."""
        if not logs:
            return
        rows = [
            {
                "id": str(_uuid.uuid4()),
                "session_id": entry["session_id"],
                "turn_number": turn_number,
                "agent_name": entry["agent_name"],
                "model": entry["model"],
                "system_prompt": entry["system_prompt"],
                "messages": entry["messages"],
                "response_content": entry["response_content"],
                "prompt_tokens": entry.get("prompt_tokens"),
                "completion_tokens": entry.get("completion_tokens"),
                "duration_ms": entry.get("duration_ms"),
                "call_sequence": entry.get("call_sequence"),
                "parent_agent": entry.get("parent_agent"),
            }
            for entry in logs
        ]
        await self._session.execute(tbl.ai_call_logs.insert(), rows)

    async def get_ai_call_logs(
        self,
        session_id: str,
        turn_number: int | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """Get AI call logs for a session, optionally filtered by turn."""
        stmt = (
            select(tbl.ai_call_logs)
            .where(tbl.ai_call_logs.c.session_id == session_id)
            .order_by(tbl.ai_call_logs.c.created_at)
            .limit(limit)
        )
        if turn_number is not None:
            stmt = stmt.where(tbl.ai_call_logs.c.turn_number == turn_number)
        ai_logs_query = await self._session.execute(stmt)
        return [dict(row) for row in ai_logs_query.mappings()]
