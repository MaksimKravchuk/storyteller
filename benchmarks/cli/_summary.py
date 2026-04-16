"""Summary-table rendering for the ``run`` subcommand."""

from __future__ import annotations

from dataclasses import dataclass

from benchmarks.cli._writer import Writer

_LABEL_COL_WIDTH = 40
_TAG_FMT = "{0:<40} {1:>5} {2:>10}"


@dataclass(frozen=True)
class RunRow:
    """One row in the run-summary table."""

    scenario_id: str
    iteration: int
    awarded: int
    base: int


def _percent(awarded: int, base: int) -> int:
    """Render a 0–100 percentage without divide-by-zero."""
    if base == 0:
        return 0
    return round(100 * awarded / base)


def _format_score(row: RunRow) -> str:
    """Format the ``awarded/base (pct%)`` cell."""
    return "{0}/{1} ({2}%)".format(row.awarded, row.base, _percent(row.awarded, row.base))


def _format_row(row: RunRow) -> str:
    """Format one summary-table row."""
    tag = "{0} ({1})".format(row.scenario_id, row.iteration)[:_LABEL_COL_WIDTH]
    return _TAG_FMT.format(tag, row.iteration, _format_score(row))


def print_summary_table(rows: list[RunRow], writer: Writer) -> None:
    """Print the run summary as a compact table."""
    if not rows:
        writer("(no scenarios run)")
        return
    writer("\n=== Summary ===")
    writer(_TAG_FMT.format("scenario (iter)", "iter", "score"))
    for row in rows:
        writer(_format_row(row))
