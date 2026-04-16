"""Scenario registry — maps scenario ids to :class:`Scenario` definitions.

Adding a scenario: create a package under ``benchmarks/scenarios/`` with
``state.py``, ``script.py``, and ``elements.py`` modules, expose a
``SCENARIO`` binding on its ``__init__.py``, and append the import to
:data:`ALL_SCENARIOS` below.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.autonomy_three_guards_tavern._scenario import SCENARIO as AUTONOMY_SCENARIO
from benchmarks.scenarios.memory_follow_up_marcus._scenario import SCENARIO as MEMORY_SCENARIO

ALL_SCENARIOS: tuple[Scenario, ...] = (
    MEMORY_SCENARIO,
    AUTONOMY_SCENARIO,
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
