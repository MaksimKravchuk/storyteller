"""Structured turn event store (dice rolls, item responses, NPC actions)."""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl

_DEFAULT_LIMIT = 500


class TurnEventStore:
    """Persists and retrieves structured per-turn events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        events: list[dict[str, Any]],
        *,
        session_id: str,
        turn_number: int | None,
        scene_number: int | None = None,
    ) -> None:
        """Batch insert turn event rows. No-op when ``events`` is empty."""
        if not events:
            return
        rows = [
            {
                "id": str(_uuid.uuid4()),
                "session_id": session_id,
                "turn_number": turn_number,
                "scene_number": scene_number,
                "event_type": entry["event_type"],
                "agent_name": entry.get("agent_name"),
                "npc_id": entry.get("npc_id"),
                "payload": entry["payload"],
                "sequence": entry.get("sequence"),
            }
            for entry in events
        ]
        await self._session.execute(tbl.turn_events.insert(), rows)

    async def get(
        self,
        session_id: str,
        *,
        turn_number: int | None = None,
        npc_id: str | None = None,
        event_type: str | None = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> list[dict]:
        """Get turn events for a session, optionally filtered by turn/npc/type."""
        conditions = [tbl.turn_events.c.session_id == session_id]
        if turn_number is not None:
            conditions.append(tbl.turn_events.c.turn_number == turn_number)
        if npc_id is not None:
            conditions.append(tbl.turn_events.c.npc_id == npc_id)
        if event_type is not None:
            conditions.append(tbl.turn_events.c.event_type == event_type)
        stmt = (
            select(tbl.turn_events)
            .where(*conditions)
            .order_by(tbl.turn_events.c.created_at, tbl.turn_events.c.sequence)
            .limit(limit)
        )
        events_query = await self._session.execute(stmt)
        return list(map(dict, events_query.mappings()))
