"""GameRepository — single persistence layer for all game data."""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as t
from db.converters import (
    game_event_to_row,
    knowledge_node_to_row,
    location_to_row,
    npc_to_row,
    player_to_row,
    row_to_game_event,
    row_to_knowledge_node,
    row_to_location,
    row_to_npc,
    row_to_player,
    row_to_scene,
    row_to_setting,
    scene_to_row,
    setting_to_row,
)
from knowledge.graph import KnowledgeGraph
from knowledge.node import EdgeType, KnowledgeNode
from models.game_state import GameState, PlayerState
from models.scene import Scene
from timeline.event import GameEvent


class GameRepository:
    """Async repository for loading/saving game state to PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── Session management ────────────────────────────────

    async def get_or_create_session(self, telegram_chat_id: int) -> dict:
        """Return session row dict, creating one if it doesn't exist."""
        stmt = pg_insert(t.sessions).values(
            id=str(_uuid.uuid4()),
            telegram_chat_id=telegram_chat_id,
        ).on_conflict_do_nothing(index_elements=["telegram_chat_id"])
        await self._s.execute(stmt)

        result = await self._s.execute(
            select(t.sessions).where(t.sessions.c.telegram_chat_id == telegram_chat_id)
        )
        row = result.mappings().one()
        return dict(row)

    async def update_session(
        self, session_id: str, *, state: str | None = None, language: str | None = None
    ) -> None:
        values: dict[str, Any] = {}
        if state is not None:
            values["state"] = state
        if language is not None:
            values["language"] = language
        if values:
            await self._s.execute(
                update(t.sessions).where(t.sessions.c.id == session_id).values(**values)
            )

    # ── Full state load ───────────────────────────────────

    async def load_game_state(
        self, session_id: str
    ) -> tuple[GameState, KnowledgeGraph, list[GameEvent]] | None:
        """Load full game state from PG. Returns None if no game exists for this session."""
        # Load game_states row
        result = await self._s.execute(
            select(t.game_states).where(t.game_states.c.session_id == session_id)
        )
        gs_row = result.mappings().first()
        if gs_row is None:
            return None
        gs_row = dict(gs_row)
        game_state_id = gs_row["id"]

        # Load setting
        result = await self._s.execute(
            select(t.settings).where(t.settings.c.game_state_id == game_state_id)
        )
        setting_row = result.mappings().first()
        if setting_row is None:
            return None
        setting = row_to_setting(dict(setting_row))

        # Load knowledge graph
        kg = KnowledgeGraph()
        result = await self._s.execute(
            select(t.knowledge_nodes).where(
                t.knowledge_nodes.c.game_state_id == game_state_id
            )
        )
        for row in result.mappings():
            node = row_to_knowledge_node(dict(row))
            kg.add_node(node)

        result = await self._s.execute(
            select(t.knowledge_edges).where(
                t.knowledge_edges.c.game_state_id == game_state_id
            )
        )
        for row in result.mappings():
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
        game_state.game_clock = gs_row["game_clock"]
        game_state.game_time = gs_row["game_time"]
        game_state.conversation_log = gs_row["conversation_log"]

        # Load player
        result = await self._s.execute(
            select(t.players).where(t.players.c.game_state_id == game_state_id)
        )
        player_row = result.mappings().first()
        if player_row:
            game_state.player = row_to_player(dict(player_row))

        # Load locations
        result = await self._s.execute(
            select(t.locations).where(t.locations.c.game_state_id == game_state_id)
        )
        for row in result.mappings():
            loc = row_to_location(dict(row))
            game_state.locations[loc.uuid] = loc

        # Load NPCs
        result = await self._s.execute(
            select(t.npcs).where(t.npcs.c.game_state_id == game_state_id)
        )
        for row in result.mappings():
            npc = row_to_npc(dict(row))
            game_state.npcs[npc.uuid] = npc

        # Load current scene
        result = await self._s.execute(
            select(t.scenes).where(
                t.scenes.c.game_state_id == game_state_id,
                t.scenes.c.is_current == True,  # noqa: E712
            )
        )
        scene_row = result.mappings().first()
        if scene_row:
            game_state.current_scene = row_to_scene(dict(scene_row))

        # Load events
        result = await self._s.execute(
            select(t.game_events).where(t.game_events.c.game_state_id == game_state_id)
        )
        events = [row_to_game_event(dict(row)) for row in result.mappings()]

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
        stmt = pg_insert(t.game_states).values(
            id=game_state.uuid,
            session_id=session_id,
            turn_count=game_state.turn_count,
            game_clock=game_state.game_clock,
            game_time=game_state.game_time,
            conversation_log=game_state.conversation_log,
        ).on_conflict_do_update(
            index_elements=["session_id"],
            set_={
                "turn_count": game_state.turn_count,
                "game_clock": game_state.game_clock,
                "game_time": game_state.game_time,
                "conversation_log": game_state.conversation_log,
            },
        ).returning(t.game_states.c.id)
        result = await self._s.execute(stmt)
        game_state_id = result.scalar_one()
        await self._s.flush()

        # Setting (upsert)
        setting_row = setting_to_row(game_state.setting, game_state_id)
        stmt = pg_insert(t.settings).values(**setting_row).on_conflict_do_update(
            index_elements=["game_state_id"],
            set_={k: v for k, v in setting_row.items() if k not in ("id", "game_state_id")},
        )
        await self._s.execute(stmt)

        # Player (upsert)
        player_row = player_to_row(game_state.player, game_state_id)
        stmt = pg_insert(t.players).values(**player_row).on_conflict_do_update(
            index_elements=["game_state_id"],
            set_={k: v for k, v in player_row.items() if k not in ("id", "game_state_id")},
        )
        await self._s.execute(stmt)

        # Locations (delete + insert)
        await self._s.execute(
            delete(t.locations).where(t.locations.c.game_state_id == game_state_id)
        )
        if game_state.locations:
            rows = [location_to_row(loc, game_state_id) for loc in game_state.locations.values()]
            await self._s.execute(t.locations.insert(), rows)

        # NPCs (delete + insert)
        await self._s.execute(
            delete(t.npcs).where(t.npcs.c.game_state_id == game_state_id)
        )
        if game_state.npcs:
            rows = [npc_to_row(npc, game_state_id) for npc in game_state.npcs.values()]
            await self._s.execute(t.npcs.insert(), rows)

        # Scenes (delete + insert current)
        await self._s.execute(
            delete(t.scenes).where(t.scenes.c.game_state_id == game_state_id)
        )
        if game_state.current_scene:
            row = scene_to_row(game_state.current_scene, game_state_id, is_current=True)
            await self._s.execute(t.scenes.insert().values(**row))

        # Knowledge nodes (delete + insert)
        await self._s.execute(
            delete(t.knowledge_nodes).where(
                t.knowledge_nodes.c.game_state_id == game_state_id
            )
        )
        nodes = knowledge_graph.all_nodes()
        if nodes:
            rows = [knowledge_node_to_row(n, game_state_id) for n in nodes]
            await self._s.execute(t.knowledge_nodes.insert(), rows)

        # Knowledge edges (delete + insert)
        await self._s.execute(
            delete(t.knowledge_edges).where(
                t.knowledge_edges.c.game_state_id == game_state_id
            )
        )
        edge_rows: list[dict] = []
        for node in nodes:
            for target_id, edge_type in knowledge_graph.get_edges_from(node.uuid):
                edge_rows.append({
                    "game_state_id": game_state_id,
                    "from_node_id": node.uuid,
                    "to_node_id": target_id,
                    "edge_type": edge_type.value,
                    "metadata_": {},
                })
        if edge_rows:
            await self._s.execute(t.knowledge_edges.insert(), edge_rows)

        # Events (delete + insert)
        await self._s.execute(
            delete(t.game_events).where(t.game_events.c.game_state_id == game_state_id)
        )
        if events:
            rows = [game_event_to_row(ev, game_state_id) for ev in events]
            await self._s.execute(t.game_events.insert(), rows)

    # ── Admin queries ─────────────────────────────────────

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """List sessions with basic game info for admin view."""
        stmt = (
            select(
                t.sessions.c.id,
                t.sessions.c.telegram_chat_id,
                t.sessions.c.state,
                t.sessions.c.language,
                t.sessions.c.created_at,
                t.sessions.c.updated_at,
                t.game_states.c.turn_count,
                t.game_states.c.game_clock,
                t.game_states.c.game_time,
            )
            .outerjoin(t.game_states, t.game_states.c.session_id == t.sessions.c.id)
            .order_by(t.sessions.c.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._s.execute(stmt)
        return [dict(row) for row in result.mappings()]

    async def get_session_detail(self, session_id: str) -> dict | None:
        """Get full session detail for admin view."""
        result = await self._s.execute(
            select(t.sessions).where(t.sessions.c.id == session_id)
        )
        session_row = result.mappings().first()
        if not session_row:
            return None
        detail: dict[str, Any] = {"session": dict(session_row)}

        # Game state
        result = await self._s.execute(
            select(t.game_states).where(t.game_states.c.session_id == session_id)
        )
        gs_row = result.mappings().first()
        if not gs_row:
            detail["game_state"] = None
            return detail
        gs_row = dict(gs_row)
        game_state_id = gs_row["id"]
        detail["game_state"] = gs_row

        # Setting
        result = await self._s.execute(
            select(t.settings).where(t.settings.c.game_state_id == game_state_id)
        )
        row = result.mappings().first()
        detail["setting"] = dict(row) if row else None

        # Player
        result = await self._s.execute(
            select(t.players).where(t.players.c.game_state_id == game_state_id)
        )
        row = result.mappings().first()
        detail["player"] = dict(row) if row else None

        # Counts
        from sqlalchemy import func

        for table_name, table in [
            ("location_count", t.locations),
            ("npc_count", t.npcs),
            ("knowledge_node_count", t.knowledge_nodes),
            ("event_count", t.game_events),
        ]:
            result = await self._s.execute(
                select(func.count()).select_from(table).where(
                    table.c.game_state_id == game_state_id
                )
            )
            detail[table_name] = result.scalar()

        return detail

    async def get_conversation_log(self, session_id: str) -> list[dict]:
        """Get conversation log for a session."""
        result = await self._s.execute(
            select(t.game_states.c.conversation_log).where(
                t.game_states.c.session_id == session_id
            )
        )
        row = result.scalar()
        return row if row else []

    async def get_npcs(self, session_id: str) -> list[dict]:
        """Get all NPCs for a session."""
        result = await self._s.execute(
            select(t.npcs)
            .join(t.game_states, t.game_states.c.id == t.npcs.c.game_state_id)
            .where(t.game_states.c.session_id == session_id)
        )
        return [dict(row) for row in result.mappings()]

    async def get_locations(self, session_id: str) -> list[dict]:
        """Get all locations for a session."""
        result = await self._s.execute(
            select(t.locations)
            .join(t.game_states, t.game_states.c.id == t.locations.c.game_state_id)
            .where(t.game_states.c.session_id == session_id)
        )
        return [dict(row) for row in result.mappings()]

    async def get_knowledge_graph(self, session_id: str) -> dict:
        """Get knowledge graph nodes and edges for a session."""
        # Get game_state_id
        result = await self._s.execute(
            select(t.game_states.c.id).where(t.game_states.c.session_id == session_id)
        )
        game_state_id = result.scalar()
        if not game_state_id:
            return {"nodes": [], "edges": []}

        result = await self._s.execute(
            select(t.knowledge_nodes).where(
                t.knowledge_nodes.c.game_state_id == game_state_id
            )
        )
        nodes = [dict(row) for row in result.mappings()]

        result = await self._s.execute(
            select(t.knowledge_edges).where(
                t.knowledge_edges.c.game_state_id == game_state_id
            )
        )
        edges = [dict(row) for row in result.mappings()]

        return {"nodes": nodes, "edges": edges}

    async def get_events(self, session_id: str) -> list[dict]:
        """Get all events for a session."""
        result = await self._s.execute(
            select(t.game_events)
            .join(t.game_states, t.game_states.c.id == t.game_events.c.game_state_id)
            .where(t.game_states.c.session_id == session_id)
            .order_by(t.game_events.c.scheduled_at)
        )
        return [dict(row) for row in result.mappings()]

    # ── AI call logs ──────────────────────────────────────

    async def save_ai_call_logs(
        self, logs: list[dict[str, Any]], turn_number: int | None = None
    ) -> None:
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
            }
            for entry in logs
        ]
        await self._s.execute(t.ai_call_logs.insert(), rows)

    async def get_ai_call_logs(
        self,
        session_id: str,
        turn_number: int | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """Get AI call logs for a session, optionally filtered by turn."""
        stmt = (
            select(t.ai_call_logs)
            .where(t.ai_call_logs.c.session_id == session_id)
            .order_by(t.ai_call_logs.c.created_at)
            .limit(limit)
        )
        if turn_number is not None:
            stmt = stmt.where(t.ai_call_logs.c.turn_number == turn_number)
        result = await self._s.execute(stmt)
        return [dict(row) for row in result.mappings()]
