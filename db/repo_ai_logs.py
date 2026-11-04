"""AI call log helpers for GameRepository."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Date, String, cast, distinct, func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl

_PROMPT_TOKENS_KEY = "prompt_tokens"
_COMPLETION_TOKENS_KEY = "completion_tokens"


class AILogStore:
    """Persists and retrieves AI call log entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        logs: list[dict[str, Any]],
        turn_number: int | None = None,
        user_id: str | None = None,
        game_state_id: str | None = None,
    ) -> None:
        """Batch insert AI call log entries with optional beta attribution."""
        if not logs:
            return
        rows = [
            {
                "id": str(_uuid.uuid4()),
                "session_id": entry["session_id"],
                "turn_number": turn_number,
                "user_id": user_id,
                "game_state_id": game_state_id,
                "agent_name": entry["agent_name"],
                "model": entry["model"],
                "system_prompt": entry["system_prompt"],
                "messages": entry["messages"],
                "response_content": entry["response_content"],
                _PROMPT_TOKENS_KEY: entry.get(_PROMPT_TOKENS_KEY),
                _COMPLETION_TOKENS_KEY: entry.get(_COMPLETION_TOKENS_KEY),
                "duration_ms": entry.get("duration_ms"),
                "call_sequence": entry.get("call_sequence"),
                "parent_agent": entry.get("parent_agent"),
            }
            for entry in logs
        ]
        await self._session.execute(tbl.ai_call_logs.insert(), rows)

    async def get(
        self,
        session_id: str,
        turn_number: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Get AI call logs for a session, optionally filtered by turn."""
        conditions = [tbl.ai_call_logs.c.session_id == session_id]
        if turn_number is not None:
            conditions.append(tbl.ai_call_logs.c.turn_number == turn_number)
        query = select(tbl.ai_call_logs).where(*conditions)
        stmt = query.order_by(tbl.ai_call_logs.c.created_at).limit(limit)
        ai_logs_query = await self._session.execute(stmt)
        return [dict(row) for row in ai_logs_query.mappings()]

    async def usage_summary(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate token usage by user, session, game, UTC day, and model."""
        stmt = _usage_summary_stmt(start_at, end_at)
        rows = await self._session.execute(stmt)
        summaries: list[dict[str, Any]] = []
        for row in rows.mappings():
            summary = dict(row)
            summary["total_tokens"] = summary[_PROMPT_TOKENS_KEY] + summary[_COMPLETION_TOKENS_KEY]
            summaries.append(summary)
        return summaries

    async def usage_by_model(self) -> list[dict[str, Any]]:
        """Aggregate all-time token usage by model only (enough for budget checks, one row per model)."""
        rows = await self._session.execute(_usage_by_model_stmt())
        return [dict(row) for row in rows.mappings()]

    async def turn_count_for_user(
        self,
        user_id: str,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        """Count successful persisted turns for a web user in a time window."""
        logs = tbl.ai_call_logs
        stmt = select(sa_func.count(distinct(_turn_count_key()))).where(
            logs.c.user_id == user_id,
            logs.c.turn_number.is_not(None),
            logs.c.created_at >= start_at,
            logs.c.created_at < end_at,
        )
        query_result = await self._session.execute(stmt)
        return int(query_result.scalar() or 0)


def _usage_conditions(start_at: datetime | None, end_at: datetime | None) -> list[Any]:
    """Build optional created_at conditions for usage summaries."""
    logs = tbl.ai_call_logs
    conditions = []
    if start_at is not None:
        conditions.append(logs.c.created_at >= start_at)
    if end_at is not None:
        conditions.append(logs.c.created_at < end_at)
    return conditions


def _turn_count_key() -> Any:
    """Return a cross-session turn identity expression for quota counts."""
    logs = tbl.ai_call_logs
    return sa_func.concat(logs.c.session_id, ":", cast(logs.c.turn_number, String))


def _usage_summary_stmt(start_at: datetime | None, end_at: datetime | None) -> Any:
    """Build the token usage aggregate statement."""
    logs = tbl.ai_call_logs
    day_expr = cast(logs.c.created_at, Date).label("utc_day")
    return (
        select(
            logs.c.user_id,
            logs.c.session_id,
            logs.c.game_state_id,
            logs.c.model,
            day_expr,
            sa_func.coalesce(sa_func.sum(logs.c.prompt_tokens), 0).label(_PROMPT_TOKENS_KEY),
            sa_func.coalesce(sa_func.sum(logs.c.completion_tokens), 0).label(_COMPLETION_TOKENS_KEY),
            sa_func.count(logs.c.id).label("call_count"),
            sa_func.min(logs.c.created_at).label("started_at"),
            sa_func.max(logs.c.created_at).label("ended_at"),
            sa_func.count()
            .filter(logs.c.prompt_tokens.is_(None) | logs.c.completion_tokens.is_(None))
            .label("missing_usage_count"),
        )
        .where(*_usage_conditions(start_at, end_at))
        .group_by(logs.c.user_id, logs.c.session_id, logs.c.game_state_id, logs.c.model, day_expr)
        .order_by(day_expr, logs.c.user_id, logs.c.model)
    )


def _usage_by_model_stmt() -> Any:
    """Build the per-model token usage statement used by the budget guard."""
    logs = tbl.ai_call_logs
    return select(
        logs.c.model,
        sa_func.coalesce(sa_func.sum(logs.c.prompt_tokens), 0).label(_PROMPT_TOKENS_KEY),
        sa_func.coalesce(sa_func.sum(logs.c.completion_tokens), 0).label(_COMPLETION_TOKENS_KEY),
        sa_func.count(logs.c.id).label("call_count"),
        sa_func.count()
        .filter(logs.c.prompt_tokens.is_(None) | logs.c.completion_tokens.is_(None))
        .label("missing_usage_count"),
    ).group_by(logs.c.model)
