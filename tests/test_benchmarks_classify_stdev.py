"""Unit tests for :func:`classify_stdev_overlap` — the k-sigma overlap rule."""

from __future__ import annotations

import allure

from benchmarks.cli._compare_classify import classify_stdev_overlap


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestClassifyStdevOverlap:
    @allure.story("Auto-compare")
    @allure.title("regression when current's k-sigma upper band sits strictly below baseline's lower band")
    def test_regression_non_overlap(self):
        # baseline 8 ± 1 = [7, 9]; current 5 ± 1 = [4, 6]; 6 < 7 → regression
        assert classify_stdev_overlap(8.0, 1.0, 5.0, 1.0) == "regression"

    @allure.story("Auto-compare")
    @allure.title("improvement when current's k-sigma lower band sits strictly above baseline's upper band")
    def test_improvement_non_overlap(self):
        # baseline 5 ± 1 = [4, 6]; current 8 ± 1 = [7, 9]; 7 > 6 → improvement
        assert classify_stdev_overlap(5.0, 1.0, 8.0, 1.0) == "improvement"

    @allure.story("Auto-compare")
    @allure.title("noise when k-sigma bands overlap (even partially)")
    def test_noise_overlap(self):
        # baseline 7 ± 1 = [6, 8]; current 6.5 ± 1 = [5.5, 7.5]; overlap on [6, 7.5]
        assert classify_stdev_overlap(7.0, 1.0, 6.5, 1.0) == "noise"

    @allure.story("Auto-compare")
    @allure.title("noise when current and baseline share the same mean regardless of stdev")
    def test_equal_means_is_noise(self):
        assert classify_stdev_overlap(7.0, 0.5, 7.0, 0.5) == "noise"

    @allure.story("Auto-compare")
    @allure.title("stdev=0 collapses to strict mean comparison (regression / improvement / equal)")
    def test_zero_stdev_collapses_to_mean(self):
        zero = float(0)
        assert classify_stdev_overlap(8.0, zero, 5.0, zero) == "regression"
        assert classify_stdev_overlap(5.0, zero, 8.0, zero) == "improvement"
        assert classify_stdev_overlap(7.0, zero, 7.0, zero) == "noise"

    @allure.story("Auto-compare")
    @allure.title("larger sigma_multiplier widens the bands, turning a previous regression into noise")
    def test_sigma_multiplier_widens_band(self):
        # baseline 7 ± 1 = [6, 8]; current 5 ± 1 = [4, 6] — touching at 6 → noise at k=1
        assert classify_stdev_overlap(7.0, 1.0, 5.0, 1.0) == "noise"
        # k=2: baseline [5, 9], current [3, 7] — still overlap → noise
        assert classify_stdev_overlap(7.0, 1.0, 5.0, 1.0, sigma_multiplier=2.0) == "noise"
        # k=0.5: baseline [6.5, 7.5], current [4.5, 5.5] — 5.5 < 6.5 → regression
        assert classify_stdev_overlap(7.0, 1.0, 5.0, 1.0, sigma_multiplier=0.5) == "regression"
