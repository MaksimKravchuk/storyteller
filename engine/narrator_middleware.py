"""Public hook for installing a narrator middleware on a :class:`GameEngine`."""

from __future__ import annotations

from typing import Any, Callable

from engine.game_engine import GameEngine

NarratorExecute = Callable[..., Any]
NarratorMiddleware = Callable[[NarratorExecute], NarratorExecute]


def install_narrator_middleware(engine: GameEngine, wrap: NarratorMiddleware) -> None:
    """Replace the engine narrator's ``execute`` with ``wrap(original)``."""
    director = engine._director
    if director is None:
        raise RuntimeError("install_narrator_middleware requires a running engine")
    narrator = director._cast.narrator
    narrator.execute = wrap(narrator.execute)
