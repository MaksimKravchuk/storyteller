"""Admin query helpers for GameRepository."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl

_COL_ID = "id"
_COL_GAME_STATE_ID = "game_state_id"


def _row_dict(row) -> dict:  # type: ignore[no-untyped-def]
    """Convert a SQLAlchemy mapping row to a plain dict."""
    return dict(row)


async def _load_first_row(session: AsyncSession, table: Any, game_state_id: str) -> dict | None:
    """Load the first row from a table filtered by game_state_id."""
    stmt = select(table).where(table.c.game_state_id == game_state_id)
    query = await session.execute(stmt)
    row = query.mappings().first()
    return _row_dict(row) if row else None


def _count_stmt(table, game_state_id: str):  # type: ignore[no-untyped-def]
    """Build a COUNT query filtered by game_state_id."""
    base = select(func.count()).select_from(table)
    return base.where(table.c.game_state_id == game_state_id)


async def _load_entity_counts(session: AsyncSession, detail: dict[str, Any], game_state_id: str) -> None:
    """Load entity counts into the detail dict."""
    count_tables = (
        ("location_count", tbl.locations),
        ("npc_count", tbl.npcs),
        ("knowledge_node_count", tbl.knowledge_nodes),
        ("event_count", tbl.game_events),
    )
    count_results = await asyncio.gather(
        *[session.execute(_count_stmt(table, game_state_id)) for _, table in count_tables],
    )
    for (label, _), count_query in zip(count_tables, count_results):
        detail[label] = count_query.scalar()


async def _populate_detail(session: AsyncSession, detail: dict[str, Any], game_state_id: str) -> None:
    """Load setting, player, and entity counts into the detail dict."""
    detail["setting"] = await _load_first_row(session, tbl.settings, game_state_id)
    detail["player"] = await _load_first_row(session, tbl.players, game_state_id)
    await _load_entity_counts(session, detail, game_state_id)


async def _joined_rows(session: AsyncSession, table: Any, session_id: str, order_col: Any = None) -> list[dict]:
    """Fetch rows from *table* joined to game_states via session_id."""
    stmt = (
        select(table)
        .join(tbl.game_states, tbl.game_states.c.id == table.c.game_state_id)
        .where(tbl.game_states.c.session_id == session_id)
    )
    if order_col is not None:
        stmt = stmt.order_by(order_col)
    rows = await session.execute(stmt)
    return list(map(_row_dict, rows.mappings()))


async def fetch_events(session: AsyncSession, session_id: str) -> list[dict]:
    """Get all events for a session."""
    return await _joined_rows(
        session,
        tbl.game_events,
        session_id,
        tbl.game_events.c.scheduled_at,
    )


class AdminQueries:
    """Read-only admin queries against the game database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
        sessions_query = await self.session.execute(stmt)
        return list(map(_row_dict, sessions_query.mappings()))

    async def get_session_detail(self, session_id: str) -> dict | None:
        """Get full session detail for admin view."""
        stmt = select(tbl.sessions).where(tbl.sessions.c.id == session_id)
        session_row = (await self.session.execute(stmt)).mappings().first()
        if not session_row:
            return None
        detail: dict[str, Any] = {"session": _row_dict(session_row)}

        gs_stmt = select(tbl.game_states).where(tbl.game_states.c.session_id == session_id)
        gs_mapping = (await self.session.execute(gs_stmt)).mappings().first()
        if not gs_mapping:
            detail["game_state"] = None
            return detail

        detail["game_state"] = _row_dict(gs_mapping)
        await _populate_detail(self.session, detail, gs_mapping[_COL_ID])
        return detail

    async def get_conversation_log(self, session_id: str) -> list[dict]:
        """Get conversation log for a session."""
        log_query = await self.session.execute(
            select(tbl.game_states.c.conversation_log).where(tbl.game_states.c.session_id == session_id),
        )
        row = log_query.scalar()
        return row if row else []

    async def get_npcs(self, session_id: str) -> list[dict]:
        """Get all NPCs for a session."""
        return await _joined_rows(self.session, tbl.npcs, session_id)

    async def get_locations(self, session_id: str) -> list[dict]:
        """Get all locations for a session."""
        return await _joined_rows(self.session, tbl.locations, session_id)

    async def get_knowledge_graph(self, session_id: str) -> dict:
        """Get knowledge graph nodes and edges for a session."""
        gs_id_stmt = select(tbl.game_states.c.id).where(
            tbl.game_states.c.session_id == session_id,
        )
        game_state_id = (await self.session.execute(gs_id_stmt)).scalar()
        if not game_state_id:
            return {"nodes": [], "edges": []}

        nodes = await self.session.execute(
            select(tbl.knowledge_nodes).where(tbl.knowledge_nodes.c.game_state_id == game_state_id),
        )
        edges_stmt = select(tbl.knowledge_edges).where(
            tbl.knowledge_edges.c.game_state_id == game_state_id,
        )
        edges = await self.session.execute(edges_stmt)
        return {
            "nodes": list(map(_row_dict, nodes.mappings())),
            "edges": list(map(_row_dict, edges.mappings())),
        }
