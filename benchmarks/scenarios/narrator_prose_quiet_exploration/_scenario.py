"""Scenario binding for the narrator-prose quiet-exploration benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.narrator_prose_quiet_exploration.elements import ELEMENTS
from benchmarks.scenarios.narrator_prose_quiet_exploration.script import SCRIPT
from benchmarks.scenarios.narrator_prose_quiet_exploration.state import build_state

SCENARIO: Scenario = Scenario(
    id="narrator_prose_quiet_exploration",
    label="Narrator prose stays evocative + grounded on a quiet, NPC-free exploration turn",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
