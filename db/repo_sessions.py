"""Session lifecycle helpers for ``GameRepository``.

Each started game gets its own ``sessions`` row, so the store exposes split
``create_*`` / ``get_latest_*`` methods instead of the old ``get_or_create_*``
accessors. Kept in its own module so session lifecycle stays cohesive and
``GameRepository`` can remain a thin facade over per-concern helpers.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl


def _row_dict(row: Any) -> dict:
    return dict(row)


async def _fetch_latest(db_session: AsyncSession, where_clause: Any) -> dict | None:
    stmt = (
        select(tbl.sessions)
        .where(where_clause)
        .order_by(tbl.sessions.c.created_at.desc(), tbl.sessions.c.id.desc())
        .limit(1)
    )
    query_result = await db_session.execute(stmt)
    row = query_result.mappings().first()
    return _row_dict(row) if row else None


async def _insert_row(db_session: AsyncSession, **player_identity: Any) -> dict:
    # Override ``server_default=func.now()`` with ``func.clock_timestamp()``:
    # ``now()`` returns the transaction start time, so two rows inserted in
    # the same unit of work (test fixtures most notably, which run each case
    # in one savepointed transaction) share a ``created_at`` and break the
    # ``ORDER BY created_at DESC`` tiebreak. ``clock_timestamp()`` is the
    # real wall clock inside a transaction. The secondary ``id DESC`` in
    # ``_fetch_latest`` catches any residual ties at microsecond resolution.
    new_row_values = {
        "id": str(_uuid.uuid4()),
        "created_at": func.clock_timestamp(),
        "updated_at": func.clock_timestamp(),
        **player_identity,
    }
    stmt = insert(tbl.sessions).values(**new_row_values).returning(tbl.sessions)
    query_result = await db_session.execute(stmt)
    return _row_dict(query_result.mappings().one())


class SessionStore:
    """Async session lifecycle operations backed by the ``sessions`` table."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._session = db_session

    async def get_latest_telegram(self, telegram_chat_id: int) -> dict | None:
        """Return the most recent session row for a telegram chat, or None."""
        return await _fetch_latest(self._session, tbl.sessions.c.telegram_chat_id == telegram_chat_id)

    async def create_telegram(self, telegram_chat_id: int) -> dict:
        """Insert a fresh session row for a telegram chat and return it."""
        return await _insert_row(self._session, telegram_chat_id=telegram_chat_id)

    async def get_latest_web(self, web_player_id: str) -> dict | None:
        """Return the most recent session row for a web player, or None."""
        return await _fetch_latest(self._session, tbl.sessions.c.web_player_id == web_player_id)

    async def create_web(self, web_player_id: str) -> dict:
        """Insert a fresh session row for a web player and return it."""
        return await _insert_row(self._session, web_player_id=web_player_id)

    async def update(
        self,
        session_id: str,
        *,
        state: str | None = None,
        language: str | None = None,
    ) -> None:
        """Update session fields (state and/or language)."""
        update_fields: dict[str, Any] = {}
        if state is not None:
            update_fields["state"] = state
        if language is not None:
            update_fields["language"] = language
        if not update_fields:
            return
        where_clause = tbl.sessions.c.id == session_id
        stmt = update(tbl.sessions).where(where_clause).values(**update_fields)
        await self._session.execute(stmt)
