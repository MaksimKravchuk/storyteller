"""Scenario binding for the Marcus memory follow-up benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.memory_follow_up_marcus.elements import ELEMENTS
from benchmarks.scenarios.memory_follow_up_marcus.script import SCRIPT
from benchmarks.scenarios.memory_follow_up_marcus.state import build_state

SCENARIO: Scenario = Scenario(
    id="memory_follow_up_marcus",
    label="Memory follow-up — Marcus recalls prior conversation",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
