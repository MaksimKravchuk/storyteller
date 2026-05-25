"""Per-turn counter for silent fallbacks and validation retries.

Mirrors :mod:`llm.call_logger`'s ``contextvars`` pattern: the counter
lives on a :class:`contextvars.ContextVar` so async tasks inside one
turn share the same mutable dict without leaking across turns. No
:mod:`threading` locks — asyncio is single-threaded.

Phase 1 (this module): metering only. Phase 2 will read these counters
to decide which silent fallbacks to harden.
"""

from __future__ import annotations

import contextvars
from typing import Literal

EventType = Literal["silent_fallback", "validation_retry", "schema_failure", "judge_error"]

_CounterKey = tuple[str, EventType]
_CounterMap = dict[_CounterKey, int]

# Per-turn counter map. ``None`` = not yet initialised (recorders no-op).
reliability_counters: contextvars.ContextVar[_CounterMap | None] = contextvars.ContextVar(
    "reliability_counters",
    default=None,
)


def reset_counters() -> None:
    """Initialise an empty counter map for a new turn."""
    reliability_counters.set({})


def _bump(agent: str, event_type: EventType) -> None:
    """Increment a single ``(agent, event_type)`` cell.

    No-op when the counter map is uninitialised — recorders may run
    in unit tests or pre-turn paths that never called
    :func:`reset_counters`. Avoiding the silent crash there is more
    important than catching a missed reset.
    """
    counters = reliability_counters.get(None)
    if counters is None:
        return
    key = (agent, event_type)
    counters[key] = counters.get(key, 0) + 1


def record_fallback(agent: str, reason: str) -> None:
    """Record one silent-fallback hit for ``agent``.

    ``reason`` is accepted for caller-site self-documentation (and
    future log-correlation hooks). It is not part of the counter key
    today — phase 1 only needs ``(agent, event_type)`` tallies — and
    asserting on it keeps the named parameter live so the public
    surface does not have to change when phase 2 routes it.
    """
    assert isinstance(reason, str)
    _bump(agent, "silent_fallback")


def record_retry(agent: str, attempt: int) -> None:
    """Record one validation retry for ``agent``.

    ``attempt`` is the 1-based attempt number; accepted for caller
    self-documentation and ignored by the key. Every retry is one
    increment regardless of which attempt produced it.
    """
    assert attempt >= 0
    _bump(agent, "validation_retry")


def record_schema_failure(agent: str, error: str) -> None:
    """Record one schema-validation failure for ``agent``.

    Reserved for phase 2 callers; defined now so the surface area
    stays stable. ``error`` is documented at the call site, not in
    the key.
    """
    assert isinstance(error, str)
    _bump(agent, "schema_failure")


def snapshot_counters() -> dict[tuple[str, str], int]:
    """Return a copy of the current counter map.

    Returns an empty dict when the buffer was never initialised so
    callers can iterate over the result unconditionally. The return
    type widens the second key element from :data:`EventType` to
    :class:`str` so callers (persistence helpers, JSON serialisers)
    don't have to round-trip through ``Literal`` narrowing.
    """
    counters = reliability_counters.get(None)
    if counters is None:
        return {}
    return {(agent, event_type): count for (agent, event_type), count in counters.items()}
