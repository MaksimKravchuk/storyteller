"""Data model for the ``benchmarks narration-diff`` subcommand."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnText:
    """One captured turn's player action + narration, for cross-version diffing."""

    index: int
    player_action: str
    narration: str


ScenarioIndex = dict[str, list[TurnText]]
