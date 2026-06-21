"""Aggregate per-iteration :class:`ScenarioReport` objects across iterations."""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass

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


@dataclass
class _ElementTally:
    """Running per-element accumulator over iterations (passes + judge votes)."""

    score: ElementScore
    passes: int
    k_yes: int
    n_votes: int


def _collect_tallies(reports: list[ScenarioReport]) -> OrderedDict[str, _ElementTally]:
    """Single-pass walk: preserve first-seen order, tally passes + judge votes."""
    tallies: OrderedDict[str, _ElementTally] = OrderedDict()
    for report in reports:
        for score in report.element_scores:
            tally = tallies.get(score.element_id)
            if tally is None:
                tally = _ElementTally(score=score, passes=0, k_yes=0, n_votes=0)
                tallies[score.element_id] = tally
            tally.passes += int(element_passed(score))
            tally.k_yes += score.k_yes
            tally.n_votes += score.n_total
    return tallies


def _pass_rates(reports: list[ScenarioReport]) -> list[ElementPassRate]:
    """Build one :class:`ElementPassRate` per element in first-seen order."""
    iterations = len(reports)
    return [
        ElementPassRate(
            element_id=tally.score.element_id,
            label=tally.score.label,
            base_value=tally.score.base_value,
            passes=tally.passes,
            iterations=iterations,
            k_yes=tally.k_yes,
            n_votes=tally.n_votes,
        )
        for tally in _collect_tallies(reports).values()
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
