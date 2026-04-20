"""Group per-iteration reports by scenario and archive aggregates."""

from __future__ import annotations

from collections import OrderedDict

from benchmarks.cli._writer import Writer
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


def finalise_aggregates(
    reports: list[ScenarioReport],
    sha: str,
    writer: Writer,
) -> list[ScenarioAggregate]:
    """Aggregate per-scenario, archive the aggregates, and return them in order."""
    aggregates: list[ScenarioAggregate] = []
    for scenario_id, scenario_reports in _group_by_scenario(reports).items():
        aggregate = aggregate_reports(scenario_reports)
        _, md_path = write_aggregate(aggregate, sha)
        writer(
            _AGGREGATE_LINE.format(
                scenario_id,
                aggregate.iterations,
                aggregate.mean_awarded,
                aggregate.min_awarded,
                aggregate.max_awarded,
                md_path,
            ),
        )
        aggregates.append(aggregate)
    return aggregates
