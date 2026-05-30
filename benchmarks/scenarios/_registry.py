"""Scenario registry — discovers :class:`Scenario` definitions from the subpackages.

Each ``benchmarks/scenarios/<name>/`` package exposes its definition as
``_scenario.SCENARIO``. They are discovered here so adding a scenario needs no
edit to this file — and the registry never accretes a per-scenario import that
would push it past the module-import budget.
"""

from __future__ import annotations

import importlib
import pkgutil

from benchmarks import scenarios as _scenarios_pkg
from benchmarks.harness.types._scenarios import Scenario

_SCENARIO_MODULE = "{0}.{1}._scenario"


def _discover_scenarios() -> tuple[Scenario, ...]:
    """Import every scenario subpackage's ``_scenario.SCENARIO``, ordered by id."""
    discovered: list[Scenario] = []
    for module_info in pkgutil.iter_modules(_scenarios_pkg.__path__):
        if not module_info.ispkg:
            continue
        module_name = _SCENARIO_MODULE.format(_scenarios_pkg.__name__, module_info.name)
        discovered.append(importlib.import_module(module_name).SCENARIO)
    return tuple(sorted(discovered, key=lambda scenario: scenario.id))


ALL_SCENARIOS: tuple[Scenario, ...] = _discover_scenarios()


def _ids() -> str:
    """Render a comma-separated list of known scenario ids."""
    return ", ".join(scenario.id for scenario in ALL_SCENARIOS)


def get_scenario(scenario_id: str) -> Scenario:
    """Look up a scenario by id. Raises ``KeyError`` on miss."""
    for candidate in ALL_SCENARIOS:
        if candidate.id == scenario_id:
            return candidate
    raise KeyError("Unknown scenario id {0!r}. Known: {1}".format(scenario_id, _ids()))
