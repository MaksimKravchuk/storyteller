"""Scenario registry — maps scenario ids to :class:`Scenario` definitions."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.autonomy_three_guards_tavern._scenario import SCENARIO as AUTONOMY_SCENARIO
from benchmarks.scenarios.escalation_guard_assault._scenario import SCENARIO as ESCALATION_SCENARIO
from benchmarks.scenarios.memory_follow_up_marcus._scenario import SCENARIO as MEMORY_SCENARIO
from benchmarks.scenarios.memory_follow_up_marcus_graph_only._scenario import SCENARIO as MEMORY_GRAPH_ONLY_SCENARIO
from benchmarks.scenarios.npc_autonomy_emergent_vendetta._scenario import SCENARIO as EMERGENT_VENDETTA_SCENARIO
from benchmarks.scenarios.npc_autonomy_murder_plot._scenario import SCENARIO as NPC_AUTONOMY_MURDER_SCENARIO

ALL_SCENARIOS: tuple[Scenario, ...] = (
    MEMORY_SCENARIO,
    MEMORY_GRAPH_ONLY_SCENARIO,
    AUTONOMY_SCENARIO,
    ESCALATION_SCENARIO,
    NPC_AUTONOMY_MURDER_SCENARIO,
    EMERGENT_VENDETTA_SCENARIO,
)


def _ids() -> str:
    """Render a comma-separated list of known scenario ids."""
    return ", ".join(scenario.id for scenario in ALL_SCENARIOS)


def get_scenario(scenario_id: str) -> Scenario:
    """Look up a scenario by id. Raises ``KeyError`` on miss."""
    for candidate in ALL_SCENARIOS:
        if candidate.id == scenario_id:
            return candidate
    raise KeyError("Unknown scenario id {0!r}. Known: {1}".format(scenario_id, _ids()))
