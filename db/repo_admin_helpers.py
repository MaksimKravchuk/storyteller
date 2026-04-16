"""Helper functions for admin queries."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl


def _row_dict(row) -> dict:  # type: ignore[no-untyped-def]
    """Convert a SQLAlchemy mapping row to a plain dict."""
    return dict(row)


async def load_first_row(session: AsyncSession, table: Any, game_state_id: str) -> dict | None:
    """Load the first row from a table filtered by game_state_id."""
    stmt = select(table).where(table.c.game_state_id == game_state_id)
    query = await session.execute(stmt)
    row = query.mappings().first()
    return _row_dict(row) if row else None


def count_stmt(table, game_state_id: str):  # type: ignore[no-untyped-def]
    """Build a COUNT query filtered by game_state_id."""
    base = select(func.count()).select_from(table)
    return base.where(table.c.game_state_id == game_state_id)


async def load_entity_counts(session: AsyncSession, detail: dict[str, Any], game_state_id: str) -> None:
    """Load entity counts into the detail dict."""
    count_tables = (
        ("location_count", tbl.locations),
        ("npc_count", tbl.npcs),
        ("knowledge_node_count", tbl.knowledge_nodes),
        ("event_count", tbl.game_events),
    )
    count_results = await asyncio.gather(
        *[session.execute(count_stmt(table, game_state_id)) for _, table in count_tables],
    )
    for (label, _), count_query in zip(count_tables, count_results):
        detail[label] = count_query.scalar()


async def populate_detail(session: AsyncSession, detail: dict[str, Any], game_state_id: str) -> None:
    """Load setting, player, and entity counts into the detail dict."""
    detail["setting"] = await load_first_row(session, tbl.settings, game_state_id)
    detail["player"] = await load_first_row(session, tbl.players, game_state_id)
    await load_entity_counts(session, detail, game_state_id)


async def joined_rows(session: AsyncSession, table: Any, session_id: str, order_col: Any = None) -> list[dict]:
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


async def joined_rows_by_gs(session: AsyncSession, table: Any, game_state_id: str) -> list[dict]:
    """Fetch every row in *table* where ``game_state_id`` matches, as plain dicts."""
    stmt = select(table).where(table.c.game_state_id == game_state_id)
    rows = await session.execute(stmt)
    return list(map(_row_dict, rows.mappings()))
