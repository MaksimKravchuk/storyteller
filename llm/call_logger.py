"""Async-safe context for capturing AI call logs during a game turn."""

from __future__ import annotations

import contextvars
from typing import Any

# Set by the Telegram bot handler before calling engine methods.
current_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_session_id", default=None)

# Accumulates log entry dicts during a turn; flushed to DB afterward.
_CallLogEntry = dict[str, Any]

call_log_buffer: contextvars.ContextVar[list[_CallLogEntry] | None] = contextvars.ContextVar(
    "call_log_buffer", default=None
)

# Stack of agent names for tracking call chains (parent→child).
agent_stack: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar("agent_stack", default=None)

# Auto-incrementing counter for ordering LLM calls within a turn.
call_sequence_counter: contextvars.ContextVar[int] = contextvars.ContextVar("call_sequence_counter", default=0)


def reset_buffer() -> None:
    """Clear the buffer and call-chain tracking for a new turn."""
    call_log_buffer.set([])
    agent_stack.set([])
    call_sequence_counter.set(0)


def get_and_clear_buffer() -> list[dict[str, Any]]:
    """Return accumulated log entries and reset the buffer."""
    buf = call_log_buffer.get(None) or []
    call_log_buffer.set(None)
    return list(buf)
