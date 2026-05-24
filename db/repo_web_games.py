"""Web story library persistence helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl


def _row_dict(row: Any) -> dict:
    return dict(row)


class WebGameStore:
    """Async operations for account-owned web story library rows."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._session = db_session

    async def list(self, web_player_id: str) -> list[dict]:
        """Return non-archived web games for one player, newest first."""
        stmt = (
            select(
                tbl.sessions.c.id,
                tbl.sessions.c.title,
                tbl.sessions.c.updated_at,
                tbl.game_states.c.id.label("game_id"),
                tbl.game_states.c.turn_count,
                tbl.settings.c.name.label("setting"),
            )
            .join(tbl.game_states, tbl.game_states.c.session_id == tbl.sessions.c.id)
            .join(tbl.settings, tbl.settings.c.game_state_id == tbl.game_states.c.id)
            .where(tbl.sessions.c.web_player_id == web_player_id)
            .where(tbl.sessions.c.archived_at.is_(None))
            .order_by(tbl.sessions.c.updated_at.desc(), tbl.sessions.c.id.desc())
        )
        query_result = await self._session.execute(stmt)
        return [_row_dict(row) for row in query_result.mappings().all()]

    async def get_by_game(self, web_player_id: str, game_id: str) -> dict | None:
        """Return an owned, non-archived web session by game id, or None."""
        stmt = (
            select(tbl.sessions)
            .join(tbl.game_states, tbl.game_states.c.session_id == tbl.sessions.c.id)
            .where(tbl.sessions.c.web_player_id == web_player_id)
            .where(tbl.sessions.c.archived_at.is_(None))
            .where(tbl.game_states.c.id == game_id)
            .limit(1)
        )
        query_result = await self._session.execute(stmt)
        row = query_result.mappings().first()
        return _row_dict(row) if row else None

    async def archive(self, web_player_id: str, game_id: str) -> bool:
        """Soft-delete an owned web game, returning False for absent/foreign ids."""
        owned_session = await self.get_by_game(web_player_id, game_id)
        if owned_session is None:
            return False
        stmt = (
            update(tbl.sessions)
            .where(tbl.sessions.c.id == owned_session["id"])
            .values(archived_at=func.clock_timestamp(), updated_at=func.clock_timestamp())
        )
        await self._session.execute(stmt)
        return True
