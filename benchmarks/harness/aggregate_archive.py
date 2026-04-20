"""Persist :class:`ScenarioAggregate` artefacts alongside per-iteration reports."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from benchmarks.harness._archive_naming import current_timestamp, sanitise_filename, sha_fragment
from benchmarks.harness.archive import write_pair
from benchmarks.harness.types._aggregates import ScenarioAggregate


def _aggregate_stem(aggregate: ScenarioAggregate, sha: str) -> str:
    return "{0}_{1}_{2}_aggregate".format(
        current_timestamp(),
        sha_fragment(sha),
        sanitise_filename(aggregate.scenario_id),
    )


def _render_markdown(aggregate: ScenarioAggregate, sha: str) -> str:
    """Render a compact aggregate report as markdown."""
    lines = [
        "# {0} — aggregate".format(aggregate.scenario_label),
        "",
        "- Scenario: `{0}`".format(aggregate.scenario_id),
        "- Iterations: {0}".format(aggregate.iterations),
        "- Engine SHA: `{0}`".format(sha or "nosha"),
        "- Total base: {0}".format(aggregate.total_base),
        "- Mean awarded: {0:.2f}".format(aggregate.mean_awarded),
        "- Range: [{0}, {1}]".format(aggregate.min_awarded, aggregate.max_awarded),
        "- Per-iteration totals: {0}".format(aggregate.iteration_totals),
        "",
        "## Element pass rates",
        "",
        "| element | base | passes |",
        "| --- | --- | --- |",
    ]
    for pass_rate in aggregate.element_pass_rates:
        lines.append(
            "| {0} | {1} | {2}/{3} |".format(
                pass_rate.label,
                pass_rate.base_value,
                pass_rate.passes,
                pass_rate.iterations,
            ),
        )
    lines.append("")
    return "\n".join(lines)


def write_aggregate(aggregate: ScenarioAggregate, sha: str) -> tuple[Path, Path]:
    """Persist a JSON + markdown aggregate next to the per-iteration files."""
    payload = asdict(aggregate)
    payload["engine_git_sha"] = sha
    return write_pair(_aggregate_stem(aggregate, sha), payload, _render_markdown(aggregate, sha))
