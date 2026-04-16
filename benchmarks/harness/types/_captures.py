"""Per-turn capture record shared between runner and scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cast.schemas.turn_outputs import TurnOutputs


@dataclass
class CapturedTurn:
    """Everything recorded for a single scenario turn.

    ``turn_outputs`` is the structured payload handed to the Narrator
    (and captured by wrapping the narrator's ``act`` method). ``narration``
    is the final rendered text returned to the player.
    """

    index: int
    player_action: str
    narration: str
    turn_outputs: "TurnOutputs"
    duration_ms: int
