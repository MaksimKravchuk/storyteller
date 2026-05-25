"""Admin user-management query helpers."""

from __future__ import annotations

from sqlalchemy import String, cast, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from db import repo_admin_helpers as helpers
from db import repo_admin_usage
from db import tables as tbl

_BACKSLASH = "\\"
_LIKE_WILDCARDS = (_BACKSLASH, "%", "_")
_CALL_COUNT_KEY = "call_count"
_SESSION_COUNT_KEY = "session_count"


def _escape_like(term: str) -> str:
    """Escape LIKE wildcards so pasted UUIDs don't behave as patterns."""
    escaped = term
    for char in _LIKE_WILDCARDS:
        escaped = escaped.replace(char, "{0}{1}".format(_BACKSLASH, char))
    return escaped


def apply_search_filter(stmt: Select, search: str) -> Select:
    """Add an ILIKE substring filter over id / web_player_id / telegram_chat_id."""
    pattern = "%{0}%".format(_escape_like(search))
    columns = (
        tbl.sessions.c.id,
        tbl.sessions.c.web_player_id,
        tbl.sessions.c.telegram_chat_id,
    )
    predicates = [cast(col, String).ilike(pattern, escape=_BACKSLASH) for col in columns]
    return stmt.where(or_(*predicates))


async def list_users(session: AsyncSession) -> list[dict]:
    """List user accounts with session counts and aggregate AI usage."""
    usage = repo_admin_usage.user_usage_subquery()
    stmt = (
        select(
            tbl.accounts.c.id,
            tbl.accounts.c.supabase_user_id,
            tbl.accounts.c.email,
            tbl.accounts.c.plan,
            tbl.accounts.c.is_admin,
            tbl.accounts.c.created_at,
            tbl.accounts.c.updated_at,
            func.count(distinct(tbl.sessions.c.id)).label(_SESSION_COUNT_KEY),
            func.coalesce(usage.c.call_count, 0).label(_CALL_COUNT_KEY),
            func.coalesce(usage.c.prompt_tokens, 0).label(repo_admin_usage._PROMPT_TOKENS_KEY),
            func.coalesce(usage.c.completion_tokens, 0).label(repo_admin_usage._COMPLETION_TOKENS_KEY),
        )
        .outerjoin(tbl.sessions, tbl.sessions.c.web_player_id == tbl.accounts.c.id)
        .outerjoin(usage, usage.c.id == cast(tbl.accounts.c.id, String))
        .group_by(tbl.accounts.c.id, usage.c.call_count, usage.c.prompt_tokens, usage.c.completion_tokens)
        .order_by(tbl.accounts.c.created_at.desc(), tbl.accounts.c.id.desc())
    )
    rows = await session.execute(stmt)
    return [repo_admin_usage.with_total_tokens(helpers._row_dict(row)) for row in rows.mappings()]


async def get_user_detail(session: AsyncSession, account_id: str) -> dict | None:
    """Return one account with aggregate AI usage and session summaries."""
    account_id_col = cast(tbl.accounts.c.id, String)
    account_rows = await session.execute(
        select(tbl.accounts).where(account_id_col == account_id),
    )
    account = account_rows.mappings().first()
    if account is None:
        return None
    return {
        "account": helpers._row_dict(account),
        "usage": await repo_admin_usage.user_usage(session, account_id),
        "sessions": await repo_admin_usage.user_sessions(session, account_id),
    }
