"""Capture :class:`TurnOutputs` per turn by wrapping the engine's Narrator.

The Director's ``PlanExecutor`` passes a :class:`TurnOutputs` payload to
``Narrator.execute`` on every turn at
``cast/director_execution.py`` line 263. We wrap that method with a
recorder that stores the payload and then delegates to the original
implementation, so we can reconstruct the full structured turn log
without modifying engine code.
"""

from __future__ import annotations

from typing import Any

from cast.schemas.turn_outputs import TurnOutputs
from engine.game_engine import GameEngine


class NarratorCapture:
    """Append-only buffer of the ``TurnOutputs`` the Narrator received.

    One instance is installed per engine via :meth:`attach`; callers
    read :attr:`outputs` after each :meth:`GameEngine.process_action`
    call to fetch the payload for that turn. We buffer the raw objects
    rather than deep copies because Narrator rendering does not mutate
    :class:`TurnOutputs` — it's a terminal consumer in the pipeline.
    """

    def __init__(self) -> None:
        self.outputs: list[TurnOutputs] = []

    def attach(self, engine: GameEngine) -> None:
        """Monkey-patch the engine's Narrator instance.

        Must be called **after** :meth:`GameEngine.restore_session` has
        wired the Director cast. We bind the original ``execute`` method
        via ``__func__`` so the wrapper stays a proper bound-method
        substitute — directly reassigning the attribute is enough
        because :mod:`cast.director_execution` accesses the narrator
        through ``self._cast.narrator.execute(...)``.
        """
        director = engine._director
        if director is None:
            raise RuntimeError("Narrator capture requires a restored engine")
        narrator = director._cast.narrator
        original = narrator.execute

        async def wrapper(input_data: Any, context: dict | None = None) -> Any:
            return await self._wrapped_execute(original, input_data, context)

        setattr(narrator, "execute", wrapper)

    def pop_next(self) -> TurnOutputs:
        """Return the next buffered :class:`TurnOutputs` in FIFO order.

        Raises ``IndexError`` when the Narrator did not run this turn —
        which would indicate a short-circuit branch (incapacitated
        player, routing bail-out) we want to surface loudly rather
        than silently paper over with a default payload.
        """
        if not self.outputs:
            raise IndexError("Narrator capture buffer is empty")
        first = self.outputs[0]
        self.outputs = self.outputs[1:]
        return first

    async def _wrapped_execute(
        self,
        original_execute: Any,
        input_data: Any,
        context: dict | None = None,
    ) -> Any:
        """Record ``TurnOutputs`` payloads then forward to the real Narrator."""
        if isinstance(input_data, TurnOutputs):
            self.outputs.append(input_data)
        return await original_execute(input_data, context or {})
