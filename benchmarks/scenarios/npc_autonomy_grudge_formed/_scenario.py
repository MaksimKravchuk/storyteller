"""Scenario binding for the off-screen grudge-formation benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.npc_autonomy_grudge_formed.elements import ELEMENTS
from benchmarks.scenarios.npc_autonomy_grudge_formed.script import SCRIPT
from benchmarks.scenarios.npc_autonomy_grudge_formed.state import build_state

SCENARIO: Scenario = Scenario(
    id="npc_autonomy_grudge_formed",
    label="NPC autonomy — a victim wounded off-screen turns on the attacker (ENEMY + KILL goal)",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
