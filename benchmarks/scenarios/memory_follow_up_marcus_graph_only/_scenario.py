"""Scenario binding for the graph-only Marcus memory follow-up benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.memory_follow_up_marcus.elements import ELEMENTS
from benchmarks.scenarios.memory_follow_up_marcus.script import SCRIPT
from benchmarks.scenarios.memory_follow_up_marcus_graph_only.state import build_state

SCENARIO: Scenario = Scenario(
    id="memory_follow_up_marcus_graph_only",
    label="Memory follow-up — Marcus recalls via graph only (no conversation_history seed)",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
