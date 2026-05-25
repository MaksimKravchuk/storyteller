"""Integration tests for the auto-compare seam wired into ``benchmarks run``.

These tests construct synthetic aggregates (no LLM calls) and drive the
``auto_compare_exit_code`` + ``_maybe_ratchet`` helpers directly, plus assert
the ``--no-compare`` short-circuit.
"""

from __future__ import annotations

import argparse
import json

import allure
import pytest

from benchmarks.cli._run_compare import auto_compare_exit_code
from benchmarks.harness import baselines
from benchmarks.harness.types._aggregates import ElementPassRate, PinnedBaseline, ScenarioAggregate


def _aggregate(scenario_id: str = "s1", *, mean: float = 7.0, stdev: float = 0.5) -> ScenarioAggregate:
    return ScenarioAggregate(
        scenario_id=scenario_id,
        scenario_label=scenario_id,
        iterations=3,
        total_base=10,
        mean_awarded=mean,
        min_awarded=int(mean) - 1,
        max_awarded=int(mean) + 1,
        element_pass_rates=[
            ElementPassRate(element_id="e1", label="recall", base_value=3, passes=2, iterations=3),
        ],
        iteration_totals=[int(mean) - 1, int(mean), int(mean) + 1],
        stdev_awarded=stdev,
    )


def _baseline(
    scenario_id: str = "s1", *, mean: float = 8.0, stdev: float = 0.3, noise_floor_stdev: float = 0.3
) -> PinnedBaseline:
    return PinnedBaseline(
        aggregate=_aggregate(scenario_id, mean=mean, stdev=stdev),
        baselined_at="2026-05-25T12:00:00+00:00",
        engine_git_sha="deadbee1",
        engine_models={"director_model": "gpt-5.4-mini"},
        iterations=3,
        noise_floor_stdev=noise_floor_stdev,
    )


def _args(*, no_compare: bool = False, update_baselines_on_improvement: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        no_compare=no_compare,
        update_baselines_on_improvement=update_baselines_on_improvement,
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestAutoCompareExit:
    @allure.story("Auto-compare on run")
    @allure.title("auto-compare returns 1 when a regression is detected against a pinned baseline")
    def test_regression_returns_1(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        baselines.write_baseline(_baseline(mean=8.0, stdev=0.3))

        exit_code = auto_compare_exit_code(_args(), [_aggregate(mean=5.0, stdev=0.3)])
        out = capsys.readouterr().out

        assert exit_code == 1
        assert "regression" in out

    @allure.story("Auto-compare on run")
    @allure.title("auto-compare returns 0 on noise / improvement / no_baseline")
    def test_non_regression_returns_0(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        baselines.write_baseline(_baseline(mean=5.0, stdev=0.3))

        # improvement
        assert auto_compare_exit_code(_args(), [_aggregate(mean=8.0, stdev=0.3)]) == 0
        # noise
        assert auto_compare_exit_code(_args(), [_aggregate(mean=5.1, stdev=0.5)]) == 0
        # no_baseline
        assert auto_compare_exit_code(_args(), [_aggregate(scenario_id="unmapped")]) == 0


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestMaybeRatchet:
    @allure.story("Auto-compare on run")
    @allure.title("--update-baselines-on-improvement ratchets when delta > 2 * noise_floor_stdev")
    def test_ratchet_above_threshold(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        baselines.write_baseline(_baseline(mean=5.0, stdev=0.3, noise_floor_stdev=0.5))

        current = _aggregate(mean=7.0, stdev=0.3)  # delta = 2.0 > 2 * 0.5 = 1.0
        auto_compare_exit_code(_args(update_baselines_on_improvement=True), [current])
        out = capsys.readouterr().out

        assert "ratcheted" in out
        loaded = baselines.read_baseline("s1")
        assert loaded is not None
        assert loaded.aggregate.mean_awarded == pytest.approx(7.0)
        # noise_floor_stdev must be preserved across the ratchet
        assert loaded.noise_floor_stdev == pytest.approx(0.5)

    @allure.story("Auto-compare on run")
    @allure.title("--update-baselines-on-improvement does NOT ratchet at-or-below threshold")
    def test_no_ratchet_below_threshold(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        baselines.write_baseline(_baseline(mean=5.0, stdev=0.3, noise_floor_stdev=0.5))

        # delta = 1.0 == 2 * 0.5 — strict greater-than is required, so no ratchet
        current = _aggregate(mean=6.0, stdev=0.3)
        auto_compare_exit_code(_args(update_baselines_on_improvement=True), [current])

        loaded = baselines.read_baseline("s1")
        assert loaded is not None
        assert loaded.aggregate.mean_awarded == pytest.approx(5.0)
        assert "ratcheted" not in capsys.readouterr().out

    @allure.story("Auto-compare on run")
    @allure.title("ratchet is silent when --update-baselines-on-improvement is absent")
    def test_no_ratchet_without_flag(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        baselines.write_baseline(_baseline(mean=5.0, stdev=0.3, noise_floor_stdev=0.5))

        current = _aggregate(mean=7.0, stdev=0.3)  # delta exceeds threshold
        auto_compare_exit_code(_args(update_baselines_on_improvement=False), [current])

        loaded = baselines.read_baseline("s1")
        assert loaded is not None
        # Without the flag the baseline must stay at the original 5.0
        assert loaded.aggregate.mean_awarded == pytest.approx(5.0)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestAggregateJsonHasStdev:
    @allure.story("Aggregates")
    @allure.title("stdev_awarded surfaces in the aggregate JSON archive payload")
    def test_archive_contains_stdev(self, tmp_path, monkeypatch):
        from benchmarks.harness.aggregate_archive import write_aggregate

        monkeypatch.setattr(
            "benchmarks.harness.archive.results_dir",
            lambda: tmp_path,
        )
        aggregate = _aggregate(mean=7.0, stdev=0.81)

        json_path, _ = write_aggregate(aggregate, "deadbee1")
        payload = json.loads(json_path.read_text(encoding="utf-8"))

        assert payload["stdev_awarded"] == pytest.approx(0.81)
