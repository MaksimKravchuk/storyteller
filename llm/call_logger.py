"""Async-safe context for capturing AI call logs during a game turn."""

from __future__ import annotations

import contextvars
from typing import Any

# Set by the Telegram bot handler before calling engine methods.
current_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_session_id", default=None
)

# Accumulates log entry dicts during a turn; flushed to DB afterward.
call_log_buffer: contextvars.ContextVar[list[dict[str, Any]]] = contextvars.ContextVar(
    "call_log_buffer", default=[]
)


def reset_buffer() -> None:
    """Clear the buffer for a new turn."""
    call_log_buffer.set([])


def get_and_clear_buffer() -> list[dict[str, Any]]:
    """Return accumulated log entries and reset the buffer."""
    buf = call_log_buffer.get([])
    call_log_buffer.set([])
    return list(buf)
