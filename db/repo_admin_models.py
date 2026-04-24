"""Per-session AI-model aggregation queries for the admin dashboard.

Lives in its own module so :class:`~db.repo_admin.AdminQueries` keeps
below flake8's method-count ceiling (WPS214).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl


async def fetch_session_models(session: AsyncSession, session_id: str) -> list[dict]:
    """Return distinct ``(agent_name, model, calls)`` rows for a session.

    Reads from ``ai_call_logs`` so the report reflects what was really
    dispatched — not what admin-settings overrides would imply today.
    """
    call_count = func.count().label("calls")
    stmt = (
        select(
            tbl.ai_call_logs.c.agent_name,
            tbl.ai_call_logs.c.model,
            call_count,
        )
        .where(tbl.ai_call_logs.c.session_id == session_id)
        .group_by(tbl.ai_call_logs.c.agent_name, tbl.ai_call_logs.c.model)
        .order_by(tbl.ai_call_logs.c.agent_name, call_count.desc())
    )
    rows_query = await session.execute(stmt)
    return [dict(row) for row in rows_query.mappings().all()]
