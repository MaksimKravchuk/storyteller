"""Capture :class:`TurnOutputs` per turn by wrapping the engine's Narrator."""

from __future__ import annotations

from typing import Any, Callable

from cast.schemas.turn_outputs import TurnOutputs
from engine.game_engine import GameEngine


class NarratorCapture:
    """Append-only buffer of the ``TurnOutputs`` the Narrator received."""

    def __init__(self) -> None:
        self.outputs: list[TurnOutputs] = []
        self._original_execute: Callable[..., Any] | None = None

    def attach(self, engine: GameEngine) -> None:
        """Install this capture as a narrator middleware on ``engine``."""
        director = engine._director
        if director is None:
            raise RuntimeError("NarratorCapture.attach requires a running engine")
        narrator = director._narrator
        narrator.execute = self._wrap(narrator.execute)

    def pop_next(self) -> TurnOutputs:
        """Return the next buffered payload (FIFO). Empty buffer raises loudly."""
        if not self.outputs:
            raise IndexError("Narrator capture buffer is empty")
        first = self.outputs[0]
        self.outputs = self.outputs[1:]
        return first

    def _wrap(self, original_execute: Callable[..., Any]) -> Callable[..., Any]:
        """Wire ``original_execute`` so future calls flow through :meth:`_run`."""
        self._original_execute = original_execute
        return self._run

    async def _run(self, input_data: Any, context: dict | None = None) -> Any:
        """Record ``TurnOutputs`` payloads then forward to the real narrator."""
        if isinstance(input_data, TurnOutputs):
            self.outputs.append(input_data)
        if self._original_execute is None:
            raise RuntimeError("NarratorCapture._run called before attach()")
        return await self._original_execute(input_data, context or {})
