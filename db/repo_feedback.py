"""Beta feedback persistence and review/export helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy import Select, desc, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl

_DEFAULT_LIMIT = 200
_MAX_LIMIT = 1000


class FeedbackStore:
    """Persistence operations for in-app beta feedback."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: str,
        user_email: str | None,
        game_id: str,
        category: str,
        message: str,
    ) -> str:
        """Store one feedback item with the current turn number when available."""
        turn_number = await self._turn_number_for_game(game_id)
        stmt = (
            insert(tbl.beta_feedback)
            .values(
                user_id=user_id,
                user_email=user_email,
                game_id=game_id,
                turn_number=turn_number,
                category=category,
                message=message,
            )
            .returning(tbl.beta_feedback.c.id)
        )
        feedback_result = await self._session.execute(stmt)
        return str(feedback_result.scalar_one())

    async def list_recent(self, limit: int = _DEFAULT_LIMIT) -> list[dict[str, Any]]:
        """Return recent feedback for admin review.

        ``account_email`` is resolved live via LEFT JOIN ``accounts`` on
        ``user_id`` (D008 prescribes the JOIN-on-demand pattern); the
        denormalized ``user_email`` is preserved as orphan fallback only.
        """
        bounded_limit = max(1, min(limit, _MAX_LIMIT))
        stmt = (
            select(
                tbl.beta_feedback.c.id,
                tbl.beta_feedback.c.user_id,
                tbl.beta_feedback.c.user_email,
                tbl.beta_feedback.c.game_id,
                tbl.beta_feedback.c.turn_number,
                tbl.beta_feedback.c.category,
                tbl.beta_feedback.c.message,
                tbl.beta_feedback.c.created_at,
                tbl.sessions.c.id.label("session_id"),
                tbl.settings.c.name.label("setting"),
                tbl.accounts.c.email.label("account_email"),
            )
            .join(tbl.game_states, tbl.game_states.c.id == tbl.beta_feedback.c.game_id)
            .join(tbl.sessions, tbl.sessions.c.id == tbl.game_states.c.session_id)
            .outerjoin(tbl.settings, tbl.settings.c.game_state_id == tbl.game_states.c.id)
            .outerjoin(tbl.accounts, tbl.accounts.c.id == tbl.beta_feedback.c.user_id)
            .order_by(desc(tbl.beta_feedback.c.created_at), desc(tbl.beta_feedback.c.id))
            .limit(bounded_limit)
        )
        feedback_result = await self._session.execute(stmt)
        return [dict(row) for row in feedback_result.mappings().all()]

    async def _turn_number_for_game(self, game_id: str) -> int | None:
        feedback_result = await self._session.execute(_turn_lookup_stmt(game_id))
        row = cast("Mapping[str, Any] | None", feedback_result.mappings().first())
        if row is None:
            return None
        raw_turn = row.get("turn_count")
        return int(raw_turn) if isinstance(raw_turn, int) else None


def _turn_lookup_stmt(game_id: str) -> Select[tuple[int]]:
    """Build the query for a game's current turn count."""
    stmt = select(tbl.game_states.c.turn_count)
    filtered_stmt = stmt.where(tbl.game_states.c.id == game_id)
    return filtered_stmt.limit(1)
