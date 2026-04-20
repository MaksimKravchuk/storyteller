"""Unit tests for benchmark CLI helpers — overrides parsing, compare command."""

from __future__ import annotations

import argparse
import json

import allure
import pytest

from benchmarks.cli._args import parse_args, resolve_iterations
from benchmarks.cli._compare import compare_command
from benchmarks.cli._compare_classify import PassRatePair, classify_pass_rate, classify_range
from benchmarks.cli._jobs import _parse_judge_overrides


class _FakeWriter:
    """Accumulates stdout lines for assertion."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, line: str) -> None:
        self.lines.append(line)


def _aggregate_payload(*, scenario_id="memory", mean=7.0, low=6, high=8, element_pass_rates=None):
    """Build a synthetic aggregate payload for compare_command tests."""
    iterations = 3
    return {
        "scenario_id": scenario_id,
        "scenario_label": scenario_id,
        "iterations": iterations,
        "total_base": 10,
        "mean_awarded": mean,
        "min_awarded": low,
        "max_awarded": high,
        "iteration_totals": [low, high, high],
        "element_pass_rates": element_pass_rates
        or [
            {
                "element_id": "e1",
                "label": "recall",
                "base_value": 3,
                "passes": 2,
                "iterations": iterations,
            },
        ],
    }


def _write_aggregate(path, **overrides):
    """Write a synthetic aggregate JSON file using overrides over the default payload."""
    path.write_text(json.dumps(_aggregate_payload(**overrides)), encoding="utf-8")


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestParseJudgeOverrides:
    @allure.story("CLI parsing")
    @allure.title("_parse_judge_overrides returns None for empty input so the default roster is used")
    def test_empty_returns_none(self):
        assert _parse_judge_overrides(None) is None
        assert _parse_judge_overrides("") is None

    @allure.story("CLI parsing")
    @allure.title("_parse_judge_overrides splits on commas and strips per-entry whitespace")
    def test_splits_and_strips(self):
        assert _parse_judge_overrides("opus, gpt-x ,haiku") == ["opus", "gpt-x", "haiku"]

    @allure.story("CLI parsing")
    @allure.title("_parse_judge_overrides drops empty entries so stray commas do not produce blank aliases")
    def test_drops_empty_entries(self):
        assert _parse_judge_overrides("opus,,haiku,") == ["opus", "haiku"]


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestRunArgs:
    @allure.story("CLI parsing")
    @allure.title("run defaults to 3 iterations when neither --quick nor --iterations is given")
    def test_default_iterations_is_three(self):
        args = parse_args(["run"])
        assert resolve_iterations(args) == 3

    @allure.story("CLI parsing")
    @allure.title("--quick forces a single iteration regardless of the default")
    def test_quick_forces_single_iteration(self):
        args = parse_args(["run", "--quick"])
        assert resolve_iterations(args) == 1

    @allure.story("CLI parsing")
    @allure.title("--quick and --iterations are mutually exclusive so intent is always unambiguous")
    def test_quick_and_iterations_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            parse_args(["run", "--quick", "--iterations", "5"])

    @allure.story("CLI parsing")
    @allure.title("--iterations rejects zero and negative counts at the argparse layer")
    def test_iterations_rejects_non_positive(self):
        with pytest.raises(SystemExit):
            parse_args(["run", "--iterations", "0"])
        with pytest.raises(SystemExit):
            parse_args(["run", "--iterations", "-3"])


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestClassifyRange:
    @allure.story("Compare command")
    @allure.title("non-overlapping current-max < baseline-min is classified as regression")
    def test_regression_when_current_max_below_baseline_min(self):
        assert classify_range(6, 8, 3, 5) == "regression"

    @allure.story("Compare command")
    @allure.title("non-overlapping current-min > baseline-max is classified as improvement")
    def test_improvement_when_current_min_above_baseline_max(self):
        assert classify_range(3, 5, 6, 8) == "improvement"

    @allure.story("Compare command")
    @allure.title("overlapping ranges are classified as noise — the signal is absent")
    def test_overlap_is_noise(self):
        assert classify_range(4, 8, 5, 9) == "noise"
        assert classify_range(5, 9, 4, 8) == "noise"
        assert classify_range(4, 8, 4, 8) == "noise"


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestClassifyPassRate:
    @allure.story("Compare command")
    @allure.title("3/3 baseline → 1/3 current is a regression (majority → minority)")
    def test_regression_on_majority_loss(self):
        pair = PassRatePair(label="e", baseline_passes=3, baseline_iters=3, current_passes=1, current_iters=3)
        assert classify_pass_rate(pair) == "regression"

    @allure.story("Compare command")
    @allure.title("2/3 baseline → 3/3 current is noise — both sides remain in the majority")
    def test_noise_when_both_majority(self):
        pair = PassRatePair(label="e", baseline_passes=2, baseline_iters=3, current_passes=3, current_iters=3)
        assert classify_pass_rate(pair) == "noise"

    @allure.story("Compare command")
    @allure.title("1/3 baseline → 3/3 current is an improvement (minority → majority)")
    def test_improvement_on_majority_gain(self):
        pair = PassRatePair(label="e", baseline_passes=1, baseline_iters=3, current_passes=3, current_iters=3)
        assert classify_pass_rate(pair) == "improvement"

    @allure.story("Compare command")
    @allure.title("Zero-iteration inputs render as - rather than silently claiming noise")
    def test_zero_iters_renders_dash(self):
        pair = PassRatePair(label="e", baseline_passes=0, baseline_iters=0, current_passes=0, current_iters=0)
        assert classify_pass_rate(pair) == "-"


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestCompareCommand:
    @allure.story("Compare command")
    @allure.title("compare_command prints baseline/current headers and a per-element pass-rate table")
    def test_happy_path_prints_table(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        current = tmp_path / "current.json"
        _write_aggregate(
            baseline,
            mean=8.0,
            low=7,
            high=9,
            element_pass_rates=[
                {"element_id": "e1", "label": "recall", "base_value": 3, "passes": 3, "iterations": 3},
            ],
        )
        _write_aggregate(
            current,
            mean=3.0,
            low=2,
            high=4,
            element_pass_rates=[
                {"element_id": "e1", "label": "recall", "base_value": 3, "passes": 0, "iterations": 3},
            ],
        )
        args = argparse.Namespace(baseline=str(baseline), current=str(current))
        writer = _FakeWriter()

        exit_code = compare_command(args, writer=writer)

        assert exit_code == 0
        assert any("Baseline:" in line for line in writer.lines)
        assert any("Current" in line for line in writer.lines)
        assert any("regression" in line for line in writer.lines)
        element_rows = [line for line in writer.lines if "recall" in line]
        assert element_rows
        assert "3/3 → 0/3" in element_rows[0]

    @allure.story("Compare command")
    @allure.title("overlapping scenario ranges render as noise in the scenario verdict")
    def test_scenario_verdict_noise_on_overlap(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        current = tmp_path / "current.json"
        _write_aggregate(baseline, mean=7.0, low=6, high=8)
        _write_aggregate(current, mean=7.5, low=7, high=9)
        args = argparse.Namespace(baseline=str(baseline), current=str(current))
        writer = _FakeWriter()

        compare_command(args, writer=writer)

        assert any("noise" in line for line in writer.lines)

    @allure.story("Compare command")
    @allure.title("compare_command raises FileNotFoundError when a report path does not exist")
    def test_missing_report_raises(self, tmp_path):
        args = argparse.Namespace(
            baseline=str(tmp_path / "missing.json"),
            current=str(tmp_path / "also-missing.json"),
        )

        with pytest.raises(FileNotFoundError, match="not found"):
            compare_command(args, writer=_FakeWriter())

    @allure.story("Compare command")
    @allure.title("compare_command raises ValueError with file context when a report is not valid JSON")
    def test_invalid_json_raises_with_context(self, tmp_path):
        broken = tmp_path / "broken.json"
        broken.write_text("{not valid", encoding="utf-8")
        good = tmp_path / "good.json"
        _write_aggregate(good)
        args = argparse.Namespace(baseline=str(broken), current=str(good))

        with pytest.raises(ValueError, match="not valid JSON"):
            compare_command(args, writer=_FakeWriter())

    @allure.story("Compare command")
    @allure.title("compare_command rejects per-iteration reports with a clear error")
    def test_rejects_per_iteration_report(self, tmp_path):
        per_iter = tmp_path / "per_iter.json"
        per_iter.write_text(
            json.dumps({"scenario_id": "x", "iteration": 0, "total_awarded": 1, "total_base": 2}),
            encoding="utf-8",
        )
        good = tmp_path / "good.json"
        _write_aggregate(good)
        args = argparse.Namespace(baseline=str(per_iter), current=str(good))

        with pytest.raises(ValueError, match="per-iteration"):
            compare_command(args, writer=_FakeWriter())
