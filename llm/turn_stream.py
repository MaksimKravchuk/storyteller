"""Turn-scoped live event channel: stage changes and Narrator text deltas.

The engine binds a sink for the duration of one streamed turn; performers
deep in the call tree emit into it without threading a callback through
every signature (same ContextVar pattern as ``llm.call_logger``). With no
sink bound every emit is a no-op, so non-streamed turns are unchanged.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Awaitable, Callable, Iterator, Protocol


class TurnStreamSink(Protocol):
    """Receiver for live turn events."""

    async def stage(self, name: str) -> None:
        """Receive a pipeline stage change (e.g. ``acting``, ``narrating``)."""

    async def delta(self, text: str) -> None:
        """Receive the next chunk of Narrator prose."""


_current_sink: contextvars.ContextVar[TurnStreamSink | None] = contextvars.ContextVar(
    "turn_stream_sink",
    default=None,
)


@contextmanager
def bound(sink: TurnStreamSink | None) -> Iterator[None]:
    """Route this context's turn events to ``sink`` (``None`` mutes them)."""
    token = _current_sink.set(sink)
    try:
        yield
    finally:
        _current_sink.reset(token)


@contextmanager
def muted(when: bool) -> Iterator[None]:
    """Mute turn events inside the block when ``when`` holds; otherwise leave the sink as is."""
    with bound(None if when else _current_sink.get()):
        yield


def current_sink() -> TurnStreamSink | None:
    """Return the sink bound to this context, if any."""
    return _current_sink.get()


async def emit_stage(name: str) -> None:
    """Report a pipeline stage change to the bound sink, if any."""
    sink = _current_sink.get()
    if sink is not None:
        await sink.stage(name)


def delta_handler() -> Callable[[str], Awaitable[None]] | None:
    """Return the bound sink's delta callback, or ``None`` when not streaming."""
    sink = _current_sink.get()
    return None if sink is None else sink.delta
