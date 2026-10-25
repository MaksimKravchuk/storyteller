"""Scenario binding for the return-visit memory benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.memory_return_visit.elements import ELEMENTS
from benchmarks.scenarios.memory_return_visit.script import SCRIPT
from benchmarks.scenarios.memory_return_visit.state import build_state

SCENARIO: Scenario = Scenario(
    id="memory_return_visit",
    label="Memory return visit — Eira recalls the player after they leave and come back",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
