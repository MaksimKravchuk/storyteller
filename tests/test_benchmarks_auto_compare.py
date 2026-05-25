"""Unit tests for the auto-compare verdict + ratchet predicate."""

from __future__ import annotations

import allure
import pytest

from benchmarks.cli import _auto_compare
from benchmarks.harness import baselines
from benchmarks.harness.types._aggregates import PinnedBaseline, ScenarioAggregate


def _aggregate(
    *,
    scenario_id: str = "s1",
    iterations: int = 3,
    mean: float = 7.0,
    stdev: float = 0.5,
) -> ScenarioAggregate:
    centre = int(round(mean))
    low = centre - 1
    high = centre + 1
    return ScenarioAggregate(
        scenario_id=scenario_id,
        scenario_label=scenario_id,
        iterations=iterations,
        total_base=10,
        mean_awarded=mean,
        min_awarded=low,
        max_awarded=high,
        element_pass_rates=[],
        iteration_totals=[low, centre, high],
        stdev_awarded=stdev,
    )


def _baseline(
    *,
    scenario_id: str = "s1",
    mean: float = 7.0,
    stdev: float = 0.5,
    noise_floor_stdev: float = 0.5,
    iterations: int = 3,
) -> PinnedBaseline:
    return PinnedBaseline(
        aggregate=_aggregate(scenario_id=scenario_id, mean=mean, stdev=stdev, iterations=iterations),
        baselined_at="2026-05-25T12:00:00+00:00",
        engine_git_sha="deadbee1",
        engine_models={"director_model": "gpt-5.4-mini"},
        iterations=iterations,
        noise_floor_stdev=noise_floor_stdev,
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestEvaluate:
    @allure.story("Auto-compare")
    @allure.title("evaluate returns no_baseline when nothing is pinned for the scenario")
    def test_no_baseline(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)

        verdicts = _auto_compare.evaluate([_aggregate(scenario_id="unknown")])

        assert len(verdicts) == 1
        assert verdicts[0].classification == "no_baseline"
        assert verdicts[0].scenario_id == "unknown"
        assert not _auto_compare.any_regression(verdicts)

    @allure.story("Auto-compare")
    @allure.title("evaluate flags regression when stdev bands do not overlap (N>=3)")
    def test_regression_stdev_band(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        baselines.write_baseline(_baseline(mean=8.0, stdev=0.3))

        current = _aggregate(mean=5.0, stdev=0.3)
        verdicts = _auto_compare.evaluate([current])

        assert verdicts[0].classification == "regression"
        assert _auto_compare.any_regression(verdicts)

    @allure.story("Auto-compare")
    @allure.title("evaluate reports improvement on a clean upward shift")
    def test_improvement(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        baselines.write_baseline(_baseline(mean=5.0, stdev=0.3))

        verdicts = _auto_compare.evaluate([_aggregate(mean=8.0, stdev=0.3)])

        assert verdicts[0].classification == "improvement"
        assert not _auto_compare.any_regression(verdicts)

    @allure.story("Auto-compare")
    @allure.title("evaluate returns noise when bands overlap")
    def test_noise_overlap(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        baselines.write_baseline(_baseline(mean=7.0, stdev=0.5))

        verdicts = _auto_compare.evaluate([_aggregate(mean=7.2, stdev=0.5)])

        assert verdicts[0].classification == "noise"

    @allure.story("Auto-compare")
    @allure.title("evaluate falls back to range classification when iterations < 3")
    def test_range_fallback_for_small_samples(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        # 2-iteration baseline + 2-iteration current — uses classify_range, not stdev
        baselines.write_baseline(_baseline(mean=8.0, stdev=float(0), iterations=2))

        current = ScenarioAggregate(
            scenario_id="s1",
            scenario_label="s1",
            iterations=2,
            total_base=10,
            mean_awarded=4.0,
            min_awarded=3,
            max_awarded=5,
            element_pass_rates=[],
            iteration_totals=[3, 5],
            stdev_awarded=1.0,
        )

        verdicts = _auto_compare.evaluate([current])

        # baseline range from helper = [7, 9]; current [3, 5] → regression by range
        assert verdicts[0].classification == "regression"

    @allure.story("Auto-compare")
    @allure.title("evaluate computes delta_vs_noise_floor against baseline noise_floor_stdev")
    def test_delta_vs_noise_floor(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        baselines.write_baseline(_baseline(mean=5.0, stdev=0.3, noise_floor_stdev=0.5))

        verdict = _auto_compare.evaluate([_aggregate(mean=7.0, stdev=0.3)])[0]

        # delta = 7 - 5 = 2; 2 / 0.5 = 4.0
        assert verdict.delta_vs_noise_floor == pytest.approx(4.0)

    @allure.story("Auto-compare")
    @allure.title("evaluate yields delta=0 when noise_floor_stdev is zero (avoids div-by-zero)")
    def test_delta_zero_when_noise_floor_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        baselines.write_baseline(_baseline(mean=5.0, stdev=0.3, noise_floor_stdev=float(0)))

        verdict = _auto_compare.evaluate([_aggregate(mean=7.0, stdev=0.3)])[0]

        assert verdict.delta_vs_noise_floor == pytest.approx(float(0))


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestAnyRegression:
    @allure.story("Auto-compare")
    @allure.title("any_regression is True when at least one verdict regresses")
    def test_true_on_any_regression(self):
        good = _auto_compare.Verdict("s1", "noise", 7.0, 7.0, float(0))
        bad = _auto_compare.Verdict("s2", "regression", 8.0, 5.0, -6.0)
        assert _auto_compare.any_regression([good, bad])

    @allure.story("Auto-compare")
    @allure.title("any_regression is False on no_baseline / noise / improvement only")
    def test_false_without_regression(self):
        verdicts = [
            _auto_compare.Verdict("s1", "no_baseline", float(0), 7.0, float(0)),
            _auto_compare.Verdict("s2", "noise", 7.0, 7.0, float(0)),
            _auto_compare.Verdict("s3", "improvement", 5.0, 7.0, 4.0),
        ]
        assert not _auto_compare.any_regression(verdicts)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestShouldRatchet:
    @allure.story("Auto-compare")
    @allure.title("should_ratchet is True when improvement delta strictly exceeds 2 * noise_floor_stdev")
    def test_ratchet_above_threshold(self):
        baseline = _baseline(mean=5.0, stdev=0.3, noise_floor_stdev=0.5)
        current = _aggregate(mean=7.0, stdev=0.3)  # delta = 2.0, 2 * 0.5 = 1.0; 2.0 > 1.0
        verdict = _auto_compare.Verdict("s1", "improvement", 5.0, 7.0, 4.0)

        assert _auto_compare.should_ratchet(verdict, baseline, current)

    @allure.story("Auto-compare")
    @allure.title("should_ratchet is False when delta is exactly at 2 * noise_floor_stdev (strict >)")
    def test_ratchet_at_threshold_is_false(self):
        baseline = _baseline(mean=5.0, stdev=0.3, noise_floor_stdev=0.5)
        current = _aggregate(mean=6.0, stdev=0.3)  # delta = 1.0 == 2 * 0.5
        verdict = _auto_compare.Verdict("s1", "improvement", 5.0, 6.0, 2.0)

        assert not _auto_compare.should_ratchet(verdict, baseline, current)

    @allure.story("Auto-compare")
    @allure.title("should_ratchet is False when the verdict is not improvement")
    def test_ratchet_requires_improvement_verdict(self):
        baseline = _baseline(mean=5.0, stdev=0.3, noise_floor_stdev=0.5)
        current = _aggregate(mean=10.0, stdev=0.3)
        for classification in ("regression", "noise", "no_baseline"):
            verdict = _auto_compare.Verdict("s1", classification, 5.0, 10.0, 10.0)
            assert not _auto_compare.should_ratchet(verdict, baseline, current)

    @allure.story("Auto-compare")
    @allure.title("should_ratchet is False when noise_floor_stdev is zero (no calibration)")
    def test_ratchet_blocked_on_zero_noise_floor(self):
        baseline = _baseline(mean=5.0, stdev=0.3, noise_floor_stdev=float(0))
        current = _aggregate(mean=10.0, stdev=0.3)
        verdict = _auto_compare.Verdict("s1", "improvement", 5.0, 10.0, float(0))

        assert not _auto_compare.should_ratchet(verdict, baseline, current)
