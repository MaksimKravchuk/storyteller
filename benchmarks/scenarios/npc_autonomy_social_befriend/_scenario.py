"""Scenario binding for the social-befriend autonomy benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.npc_autonomy_social_befriend.elements import ELEMENTS
from benchmarks.scenarios.npc_autonomy_social_befriend.script import SCRIPT
from benchmarks.scenarios.npc_autonomy_social_befriend.state import build_state

SCENARIO: Scenario = Scenario(
    id="npc_autonomy_social_befriend",
    label="NPC autonomy — a BEFRIEND goal drives social pursuit, not combat",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
