"""Cross-iteration aggregates over :class:`ScenarioReport`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ElementPassRate:
    """Per-element pass rate across N iterations of one scenario."""

    element_id: str
    label: str
    base_value: int
    passes: int
    iterations: int


@dataclass(frozen=True)
class ScenarioAggregate:
    """Mean + [min, max] totals and per-element pass rates over N iterations."""

    scenario_id: str
    scenario_label: str
    iterations: int
    total_base: int
    mean_awarded: float
    min_awarded: int
    max_awarded: int
    element_pass_rates: list[ElementPassRate]
    iteration_totals: list[int]
