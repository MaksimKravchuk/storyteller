"""Scenario binding for the three-guards autonomy benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.autonomy_three_guards_tavern.elements import ELEMENTS
from benchmarks.scenarios.autonomy_three_guards_tavern.script import SCRIPT
from benchmarks.scenarios.autonomy_three_guards_tavern.state import build_state

SCENARIO: Scenario = Scenario(
    id="autonomy_three_guards_tavern",
    label="Autonomy — two bystander guards react to a punch",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
