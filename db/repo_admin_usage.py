"""Shared admin usage aggregation helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl

_COL_ID = "id"
_PROMPT_TOKENS_KEY = "prompt_tokens"
_COMPLETION_TOKENS_KEY = "completion_tokens"
_CALL_COUNT_KEY = "call_count"
_TOTAL_TOKENS_KEY = "total_tokens"


def with_total_tokens(row: dict[str, Any]) -> dict[str, Any]:
    """Add ``total_tokens`` to a row containing prompt/completion token counts."""
    row[_TOTAL_TOKENS_KEY] = row[_PROMPT_TOKENS_KEY] + row[_COMPLETION_TOKENS_KEY]
    return row


def user_usage_subquery() -> Any:
    """Build aggregate usage subquery grouped by user id."""
    logs = tbl.ai_call_logs
    return (
        select(
            logs.c.user_id.label(_COL_ID),
            func.count(logs.c.id).label(_CALL_COUNT_KEY),
            func.coalesce(func.sum(logs.c.prompt_tokens), 0).label(_PROMPT_TOKENS_KEY),
            func.coalesce(func.sum(logs.c.completion_tokens), 0).label(_COMPLETION_TOKENS_KEY),
        )
        .group_by(logs.c.user_id)
        .subquery()
    )


def session_usage_subquery() -> Any:
    """Build aggregate usage subquery grouped by session id."""
    logs = tbl.ai_call_logs
    return (
        select(
            logs.c.session_id,
            func.count(logs.c.id).label(_CALL_COUNT_KEY),
            func.coalesce(func.sum(logs.c.prompt_tokens), 0).label(_PROMPT_TOKENS_KEY),
            func.coalesce(func.sum(logs.c.completion_tokens), 0).label(_COMPLETION_TOKENS_KEY),
        )
        .group_by(logs.c.session_id)
        .subquery()
    )


async def user_usage(session: AsyncSession, account_id: str) -> dict[str, int]:
    """Return aggregate AI usage for one user."""
    logs = tbl.ai_call_logs
    usage_rows = await session.execute(
        select(
            func.count(logs.c.id).label(_CALL_COUNT_KEY),
            func.coalesce(func.sum(logs.c.prompt_tokens), 0).label(_PROMPT_TOKENS_KEY),
            func.coalesce(func.sum(logs.c.completion_tokens), 0).label(_COMPLETION_TOKENS_KEY),
        ).where(logs.c.user_id == account_id),
    )
    row = usage_rows.mappings().first()
    if row is None:
        return _zero_usage()
    return with_total_tokens(dict(row))


async def user_sessions(session: AsyncSession, account_id: str) -> list[dict]:
    """Return session summaries and usage totals for one user."""
    usage = session_usage_subquery()
    stmt = (
        select(
            tbl.sessions.c.id,
            tbl.sessions.c.web_player_id,
            tbl.sessions.c.state,
            tbl.sessions.c.language,
            tbl.sessions.c.title,
            tbl.sessions.c.created_at,
            tbl.sessions.c.updated_at,
            tbl.game_states.c.turn_count,
            tbl.game_states.c.game_clock,
            tbl.game_states.c.game_time,
            tbl.game_states.c.conversation_log,
            tbl.game_states.c.scene_conversation_log,
            tbl.game_states.c.scene_action_log,
            func.coalesce(usage.c.call_count, 0).label(_CALL_COUNT_KEY),
            func.coalesce(usage.c.prompt_tokens, 0).label(_PROMPT_TOKENS_KEY),
            func.coalesce(usage.c.completion_tokens, 0).label(_COMPLETION_TOKENS_KEY),
        )
        .outerjoin(tbl.game_states, tbl.game_states.c.session_id == tbl.sessions.c.id)
        .outerjoin(usage, usage.c.session_id == tbl.sessions.c.id)
        .where(cast(tbl.sessions.c.web_player_id, String) == account_id)
        .order_by(tbl.sessions.c.updated_at.desc(), tbl.sessions.c.id.desc())
    )
    rows = await session.execute(stmt)
    return [with_total_tokens(dict(row)) for row in rows.mappings()]


def _zero_usage() -> dict[str, int]:
    return {
        _CALL_COUNT_KEY: 0,
        _PROMPT_TOKENS_KEY: 0,
        _COMPLETION_TOKENS_KEY: 0,
        _TOTAL_TOKENS_KEY: 0,
    }
