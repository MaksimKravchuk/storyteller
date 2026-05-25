"""Scenario binding for the npc-generator role-fidelity benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.npc_generator_role_fidelity.elements import ELEMENTS
from benchmarks.scenarios.npc_generator_role_fidelity.script import SCRIPT
from benchmarks.scenarios.npc_generator_role_fidelity.state import build_state

SCENARIO: Scenario = Scenario(
    id="npc_generator_role_fidelity",
    label="NPCGenerator materialises NPCs whose persona matches the requested role",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
