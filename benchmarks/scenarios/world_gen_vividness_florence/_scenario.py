"""Scenario binding for the world-gen vividness benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.world_gen_vividness_florence.elements import ELEMENTS
from benchmarks.scenarios.world_gen_vividness_florence.script import SCRIPT
from benchmarks.scenarios.world_gen_vividness_florence.state import build_state

SCENARIO: Scenario = Scenario(
    id="world_gen_vividness_florence",
    label="A richly-seeded setting surfaces as era-grounded scene + NPC prose",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
