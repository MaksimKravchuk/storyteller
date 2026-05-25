"""Group per-iteration reports by scenario and archive aggregates."""

from __future__ import annotations

import sys
from collections import OrderedDict

from benchmarks.harness.aggregate import aggregate_reports
from benchmarks.harness.aggregate_archive import write_aggregate
from benchmarks.harness.types._aggregates import ScenarioAggregate
from benchmarks.harness.types._scores import ScenarioReport

_AGGREGATE_LINE = "[{0}] aggregate over {1} iter(s): mean={2:.1f} range=[{3}, {4}] — wrote {5}"


def _group_by_scenario(reports: list[ScenarioReport]) -> OrderedDict[str, list[ScenarioReport]]:
    """Group per-iteration reports by scenario id, preserving first-seen order."""
    grouped: OrderedDict[str, list[ScenarioReport]] = OrderedDict()
    for report in reports:
        grouped.setdefault(report.scenario_id, []).append(report)
    return grouped


def _archive_and_log(scenario_reports: list[ScenarioReport], sha: str) -> ScenarioAggregate:
    """Aggregate one scenario, write its archive pair, log the summary line."""
    aggregate = aggregate_reports(scenario_reports)
    _, md_path = write_aggregate(
        aggregate,
        sha,
        engine_models=dict(scenario_reports[0].engine_models),
    )
    sys.stdout.write(
        _AGGREGATE_LINE.format(
            aggregate.scenario_id,
            aggregate.iterations,
            aggregate.mean_awarded,
            aggregate.min_awarded,
            aggregate.max_awarded,
            md_path,
        )
        + "\n",
    )
    return aggregate


def finalise_aggregates(
    reports: list[ScenarioReport],
    sha: str,
) -> list[ScenarioAggregate]:
    """Aggregate per-scenario, archive the aggregates, and return them in order."""
    return [_archive_and_log(scenario_reports, sha) for scenario_reports in _group_by_scenario(reports).values()]
