"""Scenario binding for the NPC-autonomy murder plot benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.npc_autonomy_murder_plot.elements import ELEMENTS
from benchmarks.scenarios.npc_autonomy_murder_plot.script import SCRIPT
from benchmarks.scenarios.npc_autonomy_murder_plot.state import build_state

SCENARIO: Scenario = Scenario(
    id="npc_autonomy_murder_plot",
    label="NPC autonomy — Brutus plots to murder Marcus while the player waits",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
