"""Dict<->dataclass serialisation for pinned baselines.

Split out of :mod:`benchmarks.harness.baselines` so the public read/write
surface stays small.
"""

from __future__ import annotations

from benchmarks.harness.types._aggregates import ElementPassRate, ScenarioAggregate

_KEY_ITERATIONS = "iterations"


def _rate_to_dict(rate: ElementPassRate) -> dict:
    """Flat dict shape for one :class:`ElementPassRate` row."""
    return {
        "element_id": rate.element_id,
        "label": rate.label,
        "base_value": rate.base_value,
        "passes": rate.passes,
        _KEY_ITERATIONS: rate.iterations,
    }


def _rate_from_dict(rate: dict) -> ElementPassRate:
    """Rebuild an :class:`ElementPassRate` from its serialised dict shape."""
    return ElementPassRate(
        element_id=rate["element_id"],
        label=rate["label"],
        base_value=rate["base_value"],
        passes=rate["passes"],
        iterations=rate[_KEY_ITERATIONS],
    )


def aggregate_to_dict(aggregate: ScenarioAggregate) -> dict:
    """Serialise a :class:`ScenarioAggregate` without losing nested rates."""
    return {
        "scenario_id": aggregate.scenario_id,
        "scenario_label": aggregate.scenario_label,
        _KEY_ITERATIONS: aggregate.iterations,
        "total_base": aggregate.total_base,
        "mean_awarded": aggregate.mean_awarded,
        "min_awarded": aggregate.min_awarded,
        "max_awarded": aggregate.max_awarded,
        "stdev_awarded": aggregate.stdev_awarded,
        "iteration_totals": list(aggregate.iteration_totals),
        "element_pass_rates": [_rate_to_dict(rate) for rate in aggregate.element_pass_rates],
    }


def aggregate_from_dict(payload: dict) -> ScenarioAggregate:
    """Rebuild a :class:`ScenarioAggregate` from a baseline JSON payload."""
    return ScenarioAggregate(
        scenario_id=payload["scenario_id"],
        scenario_label=payload["scenario_label"],
        iterations=payload[_KEY_ITERATIONS],
        total_base=payload["total_base"],
        mean_awarded=payload["mean_awarded"],
        min_awarded=payload["min_awarded"],
        max_awarded=payload["max_awarded"],
        element_pass_rates=[_rate_from_dict(rate) for rate in payload.get("element_pass_rates", [])],
        iteration_totals=list(payload.get("iteration_totals", [])),
        stdev_awarded=payload.get("stdev_awarded", float(0)),
    )
