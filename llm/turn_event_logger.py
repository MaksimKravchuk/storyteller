"""Async-safe context for capturing structured turn events (dice, items, …).

Mirrors :mod:`llm.call_logger` but carries typed producer outputs
(``ContestRoll``, ``AggressionRoll``, item responses, …) so the admin
dashboard can render them without regex-parsing prompt text.

Event shape (dict built by :func:`record_turn_event`)::

    {
        "event_type": "dice_contest" | "dice_aggression" | ...,
        "agent_name": str | None,
        "npc_id": str | None,
        "payload": dict,
        "sequence": int,
    }
"""

from __future__ import annotations

import contextvars
from typing import Any
from uuid import UUID

from llm.call_logger import agent_stack, current_session_id

_TurnEventEntry = dict[str, Any]

# Accumulates structured turn events during a turn; flushed to DB afterward.
turn_event_buffer: contextvars.ContextVar[list[_TurnEventEntry] | None] = contextvars.ContextVar(
    "turn_event_buffer",
    default=None,
)

# Auto-incrementing counter for ordering events within a turn.
# Mutable one-element list so asyncio.gather tasks share the counter.
turn_event_sequence_counter: contextvars.ContextVar[list[int]] = contextvars.ContextVar(
    "turn_event_sequence_counter",
    default=[0],
)


def _next_event_sequence() -> int:
    """Atomically read and increment the turn-event sequence counter."""
    counter = turn_event_sequence_counter.get([0])
    seq = counter[0]
    counter[0] = seq + 1
    return seq


def reset_events() -> None:
    """Clear the turn-event buffer and sequence counter for a new turn."""
    turn_event_buffer.set([])
    turn_event_sequence_counter.set([0])


def get_and_clear_events() -> list[_TurnEventEntry]:
    """Return accumulated turn events and reset the buffer."""
    buf = turn_event_buffer.get(None) or []
    turn_event_buffer.set([])
    return list(buf)


def _current_agent_name() -> str | None:
    """Return the top-of-stack agent name, or None when no agent is active."""
    stack = agent_stack.get(None) or []
    if not stack:
        return None
    return stack[-1]


def record_turn_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    npc_id: UUID | None = None,
    agent_name: str | None = None,
) -> None:
    """Append a structured event to the turn buffer.

    No-op when ``current_session_id`` is unset (e.g. unit tests that don't
    initialise the async context), so producers can call this unconditionally.
    """
    if current_session_id.get(None) is None:
        return
    buf = turn_event_buffer.get(None)
    if buf is None:
        buf = []
    buf.append(
        {
            "event_type": event_type,
            "agent_name": agent_name or _current_agent_name(),
            "npc_id": None if npc_id is None else str(npc_id),
            "payload": payload,
            "sequence": _next_event_sequence(),
        },
    )
    turn_event_buffer.set(buf)
