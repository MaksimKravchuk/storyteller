"""Admin reliability aggregation queries.

Reads ``turn_events`` rows where ``event_type = 'reliability_snapshot'``
and sums the per-``(agent, event_type)`` counters stored in
``payload.counters`` (a JSON array of ``{agent, event_type, count}``
records). Groups by a time window (24 h / 7 d / 30 d).

No DB migration required — the snapshot piggybacks on the existing
``turn_events.payload`` JSONB column per ADR-0002.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_DAYS_IN_MONTH = 30
_ONE_DAY = timedelta(hours=24)
_ONE_WEEK = timedelta(days=7)
_ONE_MONTH = timedelta(days=_DAYS_IN_MONTH)

_WINDOW_DELTAS: tuple[tuple[str, timedelta], ...] = (
    ("24h", _ONE_DAY),
    ("7d", _ONE_WEEK),
    ("30d", _ONE_MONTH),
)

_DEFAULT_WINDOW = "24h"

_QUERY = text(
    """
    SELECT
        counter->>'agent'      AS agent,
        counter->>'event_type' AS event_type,
        SUM((counter->>'count')::int) AS total
    FROM turn_events,
         jsonb_array_elements(payload->'counters') AS counter
    WHERE event_type = 'reliability_snapshot'
      AND created_at >= :since
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
)


def _delta_for_window(window: str) -> timedelta:
    """Return the timedelta for the given window key, defaulting to 24h."""
    for key, delta in _WINDOW_DELTAS:
        if key == window:
            return delta
    return _ONE_DAY


def _window_start(window: str) -> datetime:
    """Return the UTC start timestamp for the given window key."""
    return datetime.now(tz=timezone.utc) - _delta_for_window(window)


def _to_row(mapping: Any) -> dict[str, object]:
    return {
        "agent": mapping["agent"],
        "event_type": mapping["event_type"],
        "total": int(mapping["total"]),
    }


async def reliability_aggregates(
    session: AsyncSession,
    window: str = _DEFAULT_WINDOW,
) -> list[dict[str, object]]:
    """Return aggregated reliability counters for the given time window.

    Returns a list of ``{agent, event_type, total}`` dicts sorted by
    ``(agent, event_type)``. Empty list when no snapshots exist.
    ``window`` must be one of ``"24h"``, ``"7d"``, ``"30d"``; unknown
    values fall back to ``"24h"``.
    """
    since = _window_start(window)
    query_result = await session.execute(_QUERY, {"since": since})
    return [_to_row(row) for row in query_result.mappings()]


VALID_WINDOWS: frozenset[str] = frozenset(key for key, _ in _WINDOW_DELTAS)
