"""Scenario binding for the emergent-vendetta benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.npc_autonomy_emergent_vendetta.elements import ELEMENTS
from benchmarks.scenarios.npc_autonomy_emergent_vendetta.script import SCRIPT
from benchmarks.scenarios.npc_autonomy_emergent_vendetta.state import build_state

SCENARIO: Scenario = Scenario(
    id="npc_autonomy_emergent_vendetta",
    label="NPC autonomy — Brutus's vendetta goal must emerge from the engine, not the seed",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
