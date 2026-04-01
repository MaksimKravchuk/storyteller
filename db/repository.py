"""GameRepository — single persistence layer for all game data."""

from __future__ import annotations

import asyncio
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
)
from db.converters import (
    row_to_location,
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

_COL_ID = "id"
_COL_GAME_STATE_ID = "game_state_id"


def _updatable_fields(row: dict) -> dict:
    """Return row fields excluding primary/foreign key columns."""
    skip = {_COL_ID, _COL_GAME_STATE_ID}
    return {key: col_val for key, col_val in row.items() if key not in skip}


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
            sessions_filter = tbl.sessions.c.id == session_id
            stmt = update(tbl.sessions).where(sessions_filter).values(**update_fields)
            await self._session.execute(stmt)

    # ── Full state load ───────────────────────────────────

    async def load_game_state(self, session_id: str) -> tuple[GameState, KnowledgeGraph, list[GameEvent]] | None:
        """Load full game state from PG. Returns None if no game exists for this session."""
        base = await self._load_gs_and_setting(session_id)
        if base is None:
            return None
        gs_row, setting = base

        kg = await self._load_knowledge_graph(gs_row[_COL_ID])
        game_state = self._hydrate_game_state(gs_row, setting, kg)
        await self._load_entities(gs_row[_COL_ID], game_state)
        return game_state, kg, await self._load_scene_and_events(gs_row[_COL_ID], game_state)

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

        await self._persist_children(game_state_id, game_state, knowledge_graph, events)

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
        stmt = select(tbl.sessions).where(tbl.sessions.c.id == session_id)
        session_row = (await self._session.execute(stmt)).mappings().first()
        if not session_row:
            return None
        detail: dict[str, Any] = {"session": dict(session_row)}

        gs_stmt = select(tbl.game_states).where(tbl.game_states.c.session_id == session_id)
        gs_mapping = (await self._session.execute(gs_stmt)).mappings().first()
        if not gs_mapping:
            detail["game_state"] = None
            return detail

        detail["game_state"] = dict(gs_mapping)
        await self._populate_session_detail(detail, gs_mapping[_COL_ID])
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
        gs_id_stmt = select(tbl.game_states.c.id).where(
            tbl.game_states.c.session_id == session_id,
        )
        game_state_id = (await self._session.execute(gs_id_stmt)).scalar()
        if not game_state_id:
            return {"nodes": [], "edges": []}

        nodes = await self._session.execute(
            select(tbl.knowledge_nodes).where(tbl.knowledge_nodes.c.game_state_id == game_state_id)
        )
        edges_stmt = select(tbl.knowledge_edges).where(tbl.knowledge_edges.c.game_state_id == game_state_id)
        edges = await self._session.execute(edges_stmt)
        return {
            "nodes": [dict(row) for row in nodes.mappings()],
            "edges": [dict(row) for row in edges.mappings()],
        }

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

    async def save_ai_call_logs(
        self,
        logs: list[dict[str, Any]],
        turn_number: int | None = None,
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

    # ── Private helpers ───────────────────────────────────

    async def _populate_session_detail(self, detail: dict[str, Any], game_state_id: str) -> None:
        """Load setting, player, and entity counts into the detail dict."""
        detail["setting"] = await self._load_first_row(tbl.settings, game_state_id)
        detail["player"] = await self._load_first_row(tbl.players, game_state_id)
        await self._load_entity_counts(detail, game_state_id)

    async def _load_first_row(self, table: Any, game_state_id: str) -> dict | None:
        """Load the first row from a table filtered by game_state_id."""
        stmt = select(table).where(table.c.game_state_id == game_state_id)
        query = await self._session.execute(stmt)
        row = query.mappings().first()
        return dict(row) if row else None

    async def _load_entity_counts(self, detail: dict[str, Any], game_state_id: str) -> None:
        """Load entity counts into the detail dict."""
        from sqlalchemy import func

        count_tables = (
            ("location_count", tbl.locations),
            ("npc_count", tbl.npcs),
            ("knowledge_node_count", tbl.knowledge_nodes),
            ("event_count", tbl.game_events),
        )
        count_results = await asyncio.gather(
            *(
                self._session.execute(
                    select(func.count())
                    .select_from(table)
                    .where(
                        table.c.game_state_id == game_state_id,
                    )
                )
                for _, table in count_tables
            )
        )
        for (label, _), count_query in zip(count_tables, count_results):
            detail[label] = count_query.scalar()

    async def _load_gs_and_setting(self, session_id: str) -> tuple[dict, Any] | None:
        """Load game_states row and setting, or return None."""
        gs_query = await self._session.execute(
            select(tbl.game_states).where(tbl.game_states.c.session_id == session_id)
        )
        gs_mapping = gs_query.mappings().first()
        if gs_mapping is None:
            return None
        gs_row = dict(gs_mapping)

        setting_query = await self._session.execute(
            select(tbl.settings).where(tbl.settings.c.game_state_id == gs_row[_COL_ID])
        )
        setting_row = setting_query.mappings().first()
        if setting_row is None:
            return None
        return gs_row, row_to_setting(dict(setting_row))

    def _hydrate_game_state(self, gs_row: dict, setting: Any, kg: KnowledgeGraph) -> GameState:
        """Build a GameState from a DB row, setting, and knowledge graph."""
        game_state = GameState(setting=setting, knowledge_graph=kg)
        game_state.uuid = gs_row[_COL_ID]
        game_state.turn_count = gs_row["turn_count"]
        game_state.scene_number = gs_row.get("scene_number", 0)
        game_state.game_clock = gs_row["game_clock"]
        game_state.game_time = gs_row["game_time"]
        game_state.conversation_log = gs_row["conversation_log"]
        game_state.scene_conversation_log = gs_row.get("scene_conversation_log", [])
        game_state.pending_clarification = gs_row.get("pending_clarification")
        return game_state

    async def _load_knowledge_graph(self, game_state_id: str) -> KnowledgeGraph:
        """Load knowledge graph nodes and edges from the database."""
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
        return kg

    async def _load_entities(self, game_state_id: str, game_state: GameState) -> None:
        """Load player, locations, and NPCs into game_state."""
        await self._load_player(game_state_id, game_state)
        await self._load_locations(game_state_id, game_state)
        await self._load_npcs(game_state_id, game_state)

    async def _load_player(self, game_state_id: str, game_state: GameState) -> None:
        stmt = select(tbl.players).where(tbl.players.c.game_state_id == game_state_id)
        row = (await self._session.execute(stmt)).mappings().first()
        if row:
            game_state.player = row_to_player(dict(row))

    async def _load_locations(self, game_state_id: str, game_state: GameState) -> None:
        stmt = select(tbl.locations).where(tbl.locations.c.game_state_id == game_state_id)
        for row in (await self._session.execute(stmt)).mappings():
            loc = row_to_location(dict(row))
            game_state.locations[loc.uuid] = loc

    async def _load_npcs(self, game_state_id: str, game_state: GameState) -> None:
        stmt = select(tbl.npcs).where(tbl.npcs.c.game_state_id == game_state_id)
        for row in (await self._session.execute(stmt)).mappings():
            npc = row_to_npc(dict(row))
            game_state.npcs[npc.uuid] = npc

    async def _load_scene_and_events(
        self,
        game_state_id: str,
        game_state: GameState,
    ) -> list[GameEvent]:
        """Load current scene into game_state and return events list."""
        scene_query = await self._session.execute(
            select(tbl.scenes).where(
                tbl.scenes.c.game_state_id == game_state_id,
                tbl.scenes.c.is_current == True,  # noqa: E712
            )
        )
        scene_row = scene_query.mappings().first()
        if scene_row:
            game_state.current_scene = row_to_scene(dict(scene_row))

        events_query = await self._session.execute(
            select(tbl.game_events).where(tbl.game_events.c.game_state_id == game_state_id)
        )
        return [row_to_game_event(dict(event_row)) for event_row in events_query.mappings()]

    async def _persist_children(
        self,
        game_state_id: str,
        game_state: GameState,
        knowledge_graph: KnowledgeGraph,
        events: list[GameEvent],
    ) -> None:
        """Persist all child tables for a game state."""
        await self._save_setting_and_player(game_state_id, game_state)
        await self._save_world_objects(game_state_id, game_state)
        await self._save_knowledge(game_state_id, knowledge_graph)
        event_rows = [game_event_to_row(ev, game_state_id) for ev in events] if events else []
        await self._replace_rows(tbl.game_events, game_state_id, event_rows)

    async def _save_setting_and_player(self, game_state_id: str, game_state: GameState) -> None:
        """Upsert setting and player rows."""
        await self._upsert_one_to_one(tbl.settings, setting_to_row(game_state.setting, game_state_id))
        await self._upsert_one_to_one(tbl.players, player_to_row(game_state.player, game_state_id))

    async def _upsert_one_to_one(self, table: Any, row: dict) -> None:
        """Upsert a single row keyed by game_state_id."""
        stmt = (
            pg_insert(table)
            .values(**row)
            .on_conflict_do_update(
                index_elements=[_COL_GAME_STATE_ID],
                set_=_updatable_fields(row),
            )
        )
        await self._session.execute(stmt)

    async def _save_world_objects(self, game_state_id: str, game_state: GameState) -> None:
        """Replace locations, NPCs, and scene rows."""
        loc_rows = [location_to_row(loc, game_state_id) for loc in game_state.locations.values()]
        await self._replace_rows(tbl.locations, game_state_id, loc_rows)

        npc_rows = [npc_to_row(npc, game_state_id) for npc in game_state.npcs.values()]
        await self._replace_rows(tbl.npcs, game_state_id, npc_rows)

        scene_rows = (
            [scene_to_row(game_state.current_scene, game_state_id, is_current=True)] if game_state.current_scene else []
        )
        await self._replace_rows(tbl.scenes, game_state_id, scene_rows)

    async def _save_knowledge(self, game_state_id: str, knowledge_graph: KnowledgeGraph) -> None:
        """Replace knowledge nodes and edges."""
        nodes = knowledge_graph.all_nodes()
        await self._replace_rows(
            tbl.knowledge_nodes,
            game_state_id,
            [knowledge_node_to_row(node, game_state_id) for node in nodes],
        )
        await self._replace_rows(
            tbl.knowledge_edges,
            game_state_id,
            [
                {
                    "game_state_id": game_state_id,
                    "from_node_id": node.uuid,
                    "to_node_id": target_id,
                    "edge_type": edge_type.value,
                    "metadata_": {},
                }
                for node in nodes
                for target_id, edge_type in knowledge_graph.get_edges_from(node.uuid)
            ],
        )

    async def _replace_rows(self, table: Any, game_state_id: str, rows: list) -> None:
        """Delete all rows for game_state_id, then bulk-insert replacements."""
        del_stmt = delete(table).where(table.c.game_state_id == game_state_id)
        await self._session.execute(del_stmt)
        if rows:
            await self._session.execute(table.insert(), rows)
