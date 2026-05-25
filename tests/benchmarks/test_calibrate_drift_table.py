"""Unit tests for compute_drift_table, has_drift_alert, and format_drift_table.

All tests use synthetic data only — no LLM calls, no filesystem access.
Split from test_calibrate_drift.py to stay within WPS module-member limits.
"""

from __future__ import annotations

import pytest

from benchmarks.cli._calibrate_drift import (
    DriftRow,
    compute_drift_table,
    format_drift_table,
    has_drift_alert,
)
from benchmarks.cli._calibrate_io import CalibrationEntry
from benchmarks.cli._calibrate_persist import CalibrationResult
from benchmarks.harness.types._aggregates import ScenarioAggregate

_STDEV_LOW = 2.0
_STDEV_HIGH = 3.0
_STDEV_MUCH_HIGHER = 4.0
_STDEV_NEAR = 1.1
_PCT_FULL = 1.0
_PCT_HALF = 0.5
_PCT_TENTH = 0.1
_ENTRY_MEAN = 10.0
_AGGREGATE_MEAN = 70.0
_AGGREGATE_MAX = 80
_SCENARIO_A = "scene_a"
_SCENARIO_B = "scene_b"
_SCENARIO_BOTH = "scene_both"
_SCENARIO_SINGLE = "single_scenario"


def _make_entry(stdev: float) -> CalibrationEntry:
    return CalibrationEntry(
        mean=_ENTRY_MEAN,
        stdev=stdev,
        iterations=5,
        engine_git_sha="abc123",
        models={},
    )


def _make_result(scenario_id: str, stdev: float) -> CalibrationResult:
    aggregate = ScenarioAggregate(
        scenario_id=scenario_id,
        scenario_label=scenario_id,
        iterations=5,
        total_base=100,
        mean_awarded=_AGGREGATE_MEAN,
        min_awarded=60,
        max_awarded=_AGGREGATE_MAX,
        element_pass_rates=[],
        iteration_totals=[70, 70, 70, 70, 70],
        stdev_awarded=stdev,
    )
    return CalibrationResult(
        scenario_id=scenario_id,
        aggregate=aggregate,
        engine_git_sha="def456",
        engine_models={},
    )


def _no_drift_row() -> DriftRow:
    return DriftRow(scenario_id=_SCENARIO_SINGLE, stdev_old=1.0, stdev_new=_STDEV_NEAR, pct_change=_PCT_TENTH)


class TestComputeDriftTable:
    """Tests for ``compute_drift_table``."""

    def test_basic(self):
        old = {_SCENARIO_A: _make_entry(stdev=_STDEV_LOW)}
        rows = compute_drift_table(old, [_make_result(_SCENARIO_A, stdev=_STDEV_HIGH)])
        assert len(rows) == 1
        row = rows[0]
        assert row.scenario_id == _SCENARIO_A
        assert row.stdev_old == pytest.approx(_STDEV_LOW)
        assert row.stdev_new == pytest.approx(_STDEV_HIGH)
        assert row.pct_change == pytest.approx(_PCT_HALF)

    def test_skips_new_only(self):
        rows = compute_drift_table({}, [_make_result("brand_new", stdev=1.0)])
        assert rows == []

    def test_multiple_scenarios(self):
        old = {
            _SCENARIO_A: _make_entry(stdev=_STDEV_LOW),
            _SCENARIO_B: _make_entry(stdev=_STDEV_MUCH_HIGHER),
        }
        new = [_make_result(_SCENARIO_A, stdev=_STDEV_LOW), _make_result(_SCENARIO_B, stdev=_STDEV_LOW)]
        rows = compute_drift_table(old, new)
        assert len(rows) == 2
        assert {row.scenario_id for row in rows} == {_SCENARIO_A, _SCENARIO_B}

    def test_old_only_not_included(self):
        old = {"old_only": _make_entry(_STDEV_LOW), _SCENARIO_BOTH: _make_entry(_STDEV_LOW)}
        rows = compute_drift_table(old, [_make_result(_SCENARIO_BOTH, stdev=_STDEV_LOW)])
        assert len(rows) == 1
        assert rows[0].scenario_id == _SCENARIO_BOTH


class TestHasDriftAlert:
    """Tests for ``has_drift_alert``."""

    def test_true_when_any_drifted(self):
        rows = [
            _no_drift_row(),
            DriftRow(scenario_id=_SCENARIO_B, stdev_old=1.0, stdev_new=_STDEV_LOW, pct_change=_PCT_FULL),
        ]
        assert has_drift_alert(rows) is True

    def test_false_when_none_drifted(self):
        assert has_drift_alert([_no_drift_row()]) is False

    def test_false_for_empty(self):
        assert has_drift_alert([]) is False


class TestFormatDriftTable:
    """Tests for ``format_drift_table``."""

    def test_empty_returns_message(self):
        assert "no prior calibration data" in format_drift_table([])

    def test_contains_header_columns(self):
        rows = [DriftRow(scenario_id=_SCENARIO_A, stdev_old=1.0, stdev_new=_STDEV_LOW, pct_change=_PCT_FULL)]
        output = format_drift_table(rows)
        assert "scenario" in output
        assert "stdev_old" in output
        assert "stdev_new" in output
        assert "pct_change" in output

    def test_alert_yes_on_drift(self):
        rows = [DriftRow(scenario_id=_SCENARIO_A, stdev_old=1.0, stdev_new=_STDEV_LOW, pct_change=_PCT_FULL)]
        assert "YES" in format_drift_table(rows)

    def test_alert_no_on_no_drift(self):
        assert " no" in format_drift_table([_no_drift_row()])

    def test_ends_with_newline(self):
        rows = [DriftRow(scenario_id=_SCENARIO_SINGLE, stdev_old=1.0, stdev_new=1.0, pct_change=0)]
        assert format_drift_table(rows).endswith("\n")
