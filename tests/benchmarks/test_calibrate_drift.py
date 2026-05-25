"""Unit tests for drift detection: DriftRow and pct_change helpers.

All tests use synthetic data only — no LLM calls, no filesystem access.
"""

from __future__ import annotations

import pytest

from benchmarks.cli._calibrate_drift import (
    DriftRow,
    _DRIFT_THRESHOLD,
    _pct_change,
)

_STDEV_LOW = 2.0
_STDEV_HIGH = 3.0
_STDEV_MUCH_HIGHER = 4.0
_STDEV_SAME = 5.0
_STDEV_NEAR = 2.4
_STDEV_NEAR_PCT = 0.2
_PCT_HALF = 0.5
_PCT_FULL = 1.0
_PCT_NEG = -0.75
_SCENARIO_SINGLE = "single_scenario"


class TestPctChange:
    """Tests for the ``_pct_change`` helper."""

    def test_increase(self):
        assert _pct_change(_STDEV_LOW, _STDEV_HIGH) == pytest.approx(_PCT_HALF)

    def test_decrease(self):
        assert _pct_change(_STDEV_MUCH_HIGHER, _STDEV_LOW) == pytest.approx(-_PCT_HALF)

    def test_no_change(self):
        assert _pct_change(_STDEV_SAME, _STDEV_SAME) == pytest.approx(0)

    def test_zero_old_returns_zero(self):
        assert _pct_change(0, _STDEV_HIGH) == pytest.approx(0)


class TestDriftRowDrifted:
    """Tests for ``DriftRow.drifted``."""

    def test_drifted_exact_threshold(self):
        row = DriftRow(
            scenario_id=_SCENARIO_SINGLE,
            stdev_old=_STDEV_LOW,
            stdev_new=_STDEV_HIGH,
            pct_change=_DRIFT_THRESHOLD,
        )
        assert row.drifted is True

    def test_drifted_above_threshold(self):
        row = DriftRow(scenario_id=_SCENARIO_SINGLE, stdev_old=1.0, stdev_new=_STDEV_LOW, pct_change=_PCT_FULL)
        assert row.drifted is True

    def test_not_drifted_below_threshold(self):
        row = DriftRow(
            scenario_id=_SCENARIO_SINGLE,
            stdev_old=_STDEV_LOW,
            stdev_new=_STDEV_NEAR,
            pct_change=_STDEV_NEAR_PCT,
        )
        assert row.drifted is False

    def test_drifted_negative_direction(self):
        row = DriftRow(scenario_id=_SCENARIO_SINGLE, stdev_old=_STDEV_MUCH_HIGHER, stdev_new=1.0, pct_change=_PCT_NEG)
        assert row.drifted is True
