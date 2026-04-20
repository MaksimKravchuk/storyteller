"""Summary-table rendering for the ``run`` subcommand."""

from __future__ import annotations

from benchmarks.cli._writer import Writer
from benchmarks.harness.types._aggregates import ScenarioAggregate

_LABEL_COL_WIDTH = 40
_HEADER_FMT = "{0:<40} {1:>5} {2:>8} {3:>10}"
_ROW_FMT = "{0:<40} {1:>5} {2:>8} {3:>10}"


def _percent(awarded: float, base: int) -> int:
    """Render a 0–100 percentage without divide-by-zero."""
    if base == 0:
        return 0
    return round(100 * awarded / base)


def _format_mean_cell(aggregate: ScenarioAggregate) -> str:
    """Format the ``mean/base (pct%)`` cell."""
    return "{0:.1f}/{1} ({2}%)".format(
        aggregate.mean_awarded,
        aggregate.total_base,
        _percent(aggregate.mean_awarded, aggregate.total_base),
    )


def _format_range_cell(aggregate: ScenarioAggregate) -> str:
    """Format the ``[min, max]`` cell."""
    return "[{0}, {1}]".format(aggregate.min_awarded, aggregate.max_awarded)


def _format_aggregate_row(aggregate: ScenarioAggregate) -> str:
    """Format one aggregate summary row."""
    label = aggregate.scenario_id[:_LABEL_COL_WIDTH]
    return _ROW_FMT.format(
        label,
        aggregate.iterations,
        _format_range_cell(aggregate),
        _format_mean_cell(aggregate),
    )


def _format_element_line(scenario_id: str, pass_rate) -> str:
    """Format one per-element pass-rate line."""
    return "  [{0}] {1}: {2}/{3}".format(
        scenario_id,
        pass_rate.label,
        pass_rate.passes,
        pass_rate.iterations,
    )


def print_summary_table(aggregates: list[ScenarioAggregate], writer: Writer) -> None:
    """Print the run summary as a compact aggregate table."""
    if not aggregates:
        writer("(no scenarios run)")
        return
    writer("\n=== Summary (mean over N iterations) ===")
    writer(_HEADER_FMT.format("scenario", "iters", "range", "mean"))
    for aggregate in aggregates:
        writer(_format_aggregate_row(aggregate))
    writer("\n=== Per-element pass rates ===")
    for aggregate in aggregates:
        for pass_rate in aggregate.element_pass_rates:
            writer(_format_element_line(aggregate.scenario_id, pass_rate))
