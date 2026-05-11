"""Scenario binding for the player-appearance benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.player_appearance_in_scene.elements import ELEMENTS
from benchmarks.scenarios.player_appearance_in_scene.script import SCRIPT
from benchmarks.scenarios.player_appearance_in_scene.state import build_state

SCENARIO: Scenario = Scenario(
    id="player_appearance_in_scene",
    label="Player appearance — Cassia reacts to a foreign visitor across a scene",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
