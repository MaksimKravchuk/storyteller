"""Helper functions for saving game state to the database."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

_COL_ID = "id"
_COL_GAME_STATE_ID = "game_state_id"


def updatable_fields(row: dict) -> dict:
    """Return row fields excluding primary/foreign key columns."""
    skip = {_COL_ID, _COL_GAME_STATE_ID}
    return {key: col_val for key, col_val in row.items() if key not in skip}


async def replace_rows(session: AsyncSession, table: Any, game_state_id: str, rows: list) -> None:
    """Delete all rows for game_state_id, then bulk-insert replacements."""
    del_stmt = delete(table).where(table.c.game_state_id == game_state_id)
    await session.execute(del_stmt)
    if rows:
        await session.execute(table.insert(), rows)


async def upsert_one_to_one(session: AsyncSession, table: Any, row: dict) -> None:
    """Upsert a single row keyed by game_state_id."""
    stmt = (
        pg_insert(table)
        .values(**row)
        .on_conflict_do_update(
            index_elements=[_COL_GAME_STATE_ID],
            set_=updatable_fields(row),
        )
    )
    await session.execute(stmt)
