"""Aggregate per-iteration :class:`ScenarioReport` objects across iterations."""

from __future__ import annotations

import math
from collections import OrderedDict

from benchmarks.harness.types._aggregates import ElementPassRate, ScenarioAggregate
from benchmarks.harness.types._scores import ElementScore, ScenarioReport


def _population_stdev(totals: list[int]) -> float:
    """Compute the population standard deviation of ``totals`` (0 on N<=1)."""
    if len(totals) <= 1:
        return float(0)
    mean = sum(totals) / len(totals)
    squared_deviations = [(total - mean) ** 2 for total in totals]
    variance = sum(squared_deviations) / len(totals)
    return math.sqrt(variance)


def element_passed(score: ElementScore) -> bool:
    """Return ``True`` when an element earned at least half of its base credit.

    Majority-credit (not strict full-credit) matches the evidence-LLM majority rule
    in :func:`benchmarks.harness.scoring._aggregate_verdict` and keeps the pass-rate
    metric meaningful for >3-judge panels, where full credit rarely rounds up.
    """
    if score.base_value <= 0:
        return False
    return 2 * score.awarded >= score.base_value


def _collect_pass_counts(
    reports: list[ScenarioReport],
) -> OrderedDict[str, tuple[ElementScore, int]]:
    """Single-pass walk: preserve first-seen order and tally passes per element."""
    accumulator: OrderedDict[str, tuple[ElementScore, int]] = OrderedDict()
    for report in reports:
        for score in report.element_scores:
            first_score, count = accumulator.get(score.element_id, (score, 0))
            accumulator[score.element_id] = (first_score, count + int(element_passed(score)))
    return accumulator


def _pass_rates(reports: list[ScenarioReport]) -> list[ElementPassRate]:
    """Build one :class:`ElementPassRate` per element in first-seen order."""
    iterations = len(reports)
    return [
        ElementPassRate(
            element_id=score.element_id,
            label=score.label,
            base_value=score.base_value,
            passes=count,
            iterations=iterations,
        )
        for score, count in _collect_pass_counts(reports).values()
    ]


def aggregate_reports(reports: list[ScenarioReport]) -> ScenarioAggregate:
    """Roll up N :class:`ScenarioReport` objects for one scenario into a summary."""
    if not reports:
        raise ValueError("aggregate_reports requires at least one report")
    scenario_ids = {report.scenario_id for report in reports}
    if len(scenario_ids) != 1:
        raise ValueError(
            "aggregate_reports requires one scenario; got {0}".format(sorted(scenario_ids)),
        )
    totals = [report.total_awarded for report in reports]
    head = reports[0]
    return ScenarioAggregate(
        scenario_id=head.scenario_id,
        scenario_label=head.scenario_label,
        iterations=len(reports),
        total_base=head.total_base,
        mean_awarded=sum(totals) / len(totals),
        min_awarded=min(totals),
        max_awarded=max(totals),
        element_pass_rates=_pass_rates(reports),
        iteration_totals=totals,
        stdev_awarded=_population_stdev(totals),
    )
