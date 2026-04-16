"""Per-turn capture record shared between runner and scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cast.schemas.turn_outputs import TurnOutputs


@dataclass(frozen=True)
class CapturedTurn:
    """Everything recorded for a single scenario turn."""

    index: int
    player_action: str
    narration: str
    turn_outputs: "TurnOutputs"
    duration_ms: int
