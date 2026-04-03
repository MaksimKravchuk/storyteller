"""AI call log helpers for GameRepository."""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl


def _row_dict(row) -> dict:  # type: ignore[no-untyped-def]
    """Convert a SQLAlchemy mapping row to a plain dict."""
    return dict(row)


class AILogStore:
    """Persists and retrieves AI call log entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        logs: list[dict[str, Any]],
        turn_number: int | None = None,
    ) -> None:
        """Batch insert AI call log entries."""
        if not logs:
            return
        rows = [
            {
                "id": str(_uuid.uuid4()),
                "session_id": entry["session_id"],
                "turn_number": turn_number,
                "agent_name": entry["agent_name"],
                "model": entry["model"],
                "system_prompt": entry["system_prompt"],
                "messages": entry["messages"],
                "response_content": entry["response_content"],
                "prompt_tokens": entry.get("prompt_tokens"),
                "completion_tokens": entry.get("completion_tokens"),
                "duration_ms": entry.get("duration_ms"),
                "call_sequence": entry.get("call_sequence"),
                "parent_agent": entry.get("parent_agent"),
            }
            for entry in logs
        ]
        await self._session.execute(tbl.ai_call_logs.insert(), rows)

    async def max_call_sequence(self, session_id: str, turn_number: int | None) -> int | None:
        """Return the highest call_sequence for a session+turn, or None."""
        logs = tbl.ai_call_logs
        stmt = select(sa_func.max(logs.c.call_sequence)).where(
            logs.c.session_id == session_id,
        )
        if turn_number is None:
            turn_filter = logs.c.turn_number.is_(None)
        else:
            turn_filter = logs.c.turn_number == turn_number
        stmt = stmt.where(turn_filter)
        query = await self._session.execute(stmt)
        return query.scalar()

    async def get(
        self,
        session_id: str,
        turn_number: int | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """Get AI call logs for a session, optionally filtered by turn."""
        conditions = [tbl.ai_call_logs.c.session_id == session_id]
        if turn_number is not None:
            conditions.append(tbl.ai_call_logs.c.turn_number == turn_number)
        query = select(tbl.ai_call_logs).where(*conditions)
        stmt = query.order_by(tbl.ai_call_logs.c.created_at).limit(limit)
        ai_logs_query = await self._session.execute(stmt)
        return list(map(_row_dict, ai_logs_query.mappings()))
