"""Drift detection for ``benchmarks calibrate --compare-to-baselines``.

Compares freshly-computed stdev values (from :class:`CalibrationResult`) against
the stdev values stored in ``.calibration.json`` (previous run).  A drift alert
fires when any scenario's stdev changes by ≥ 50% (in either direction).

This module contains only pure-Python logic — no LLM calls, no filesystem I/O.
The caller is responsible for passing in the data; this module just computes.
"""

from __future__ import annotations

from dataclasses import dataclass

from benchmarks.cli._calibrate_io import CalibrationEntry
from benchmarks.cli._calibrate_persist import CalibrationResult

_DRIFT_THRESHOLD = 0.5
_SEPARATOR = " | "
_NO_PRIOR_DATA_MESSAGE = "no prior calibration data to compare against\n"
_TABLE_HEADER = ("scenario", "stdev_old", "stdev_new", "pct_change", "alert")
_TABLE_DASHES = ("--------", "---------", "---------", "----------", "-----")


@dataclass(frozen=True)
class DriftRow:
    """Drift comparison for one scenario."""

    scenario_id: str
    stdev_old: float
    stdev_new: float
    pct_change: float

    @property
    def drifted(self) -> bool:
        """Return ``True`` when the absolute %-change meets or exceeds the threshold."""
        return abs(self.pct_change) >= _DRIFT_THRESHOLD


def _pct_change(old: float, new: float) -> float:
    """Compute signed fractional change ((new - old) / old).

    Returns ``old`` (i.e. ``0.0``) when ``old`` is zero to avoid division-by-zero.
    """
    if not old:
        return old
    return (new - old) / old


def compute_drift_table(
    old_entries: dict[str, CalibrationEntry],
    new_results: list[CalibrationResult],
) -> list[DriftRow]:
    """Return a drift row for every scenario present in *both* old and new data.

    Scenarios that exist only in the new calibration (no prior baseline) are
    skipped — there is nothing to compare against.
    """
    rows: list[DriftRow] = []
    for new_result in new_results:
        old = old_entries.get(new_result.scenario_id)
        if old is None:
            continue
        pct = _pct_change(old.stdev, new_result.aggregate.stdev_awarded)
        rows.append(
            DriftRow(
                scenario_id=new_result.scenario_id,
                stdev_old=old.stdev,
                stdev_new=new_result.aggregate.stdev_awarded,
                pct_change=pct,
            )
        )
    return rows


def has_drift_alert(rows: list[DriftRow]) -> bool:
    """Return ``True`` if any row exceeds the drift threshold."""
    return any(row.drifted for row in rows)


def _row_line(row: DriftRow) -> str:
    """Render a single drift row as a markdown table line."""
    alert = "YES" if row.drifted else "no"
    return _SEPARATOR.join(
        [
            row.scenario_id,
            "{0:.4f}".format(row.stdev_old),
            "{0:.4f}".format(row.stdev_new),
            "{0:+.1%}".format(row.pct_change),
            alert,
        ]
    )


def _build_table_lines(rows: list[DriftRow]) -> list[str]:
    """Build a list of formatted table lines (header + data rows + trailing empty string)."""
    lines = [_SEPARATOR.join(_TABLE_HEADER), _SEPARATOR.join(_TABLE_DASHES)]
    for row in rows:
        lines.append(_row_line(row))
    lines.append("")
    return lines


def format_drift_table(rows: list[DriftRow]) -> str:
    """Render the drift table as a plain-text string suitable for stdout or a GH issue body."""
    if not rows:
        return _NO_PRIOR_DATA_MESSAGE
    return "\n".join(_build_table_lines(rows))
