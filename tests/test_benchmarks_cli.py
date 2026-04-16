"""Unit tests for benchmark CLI helpers — overrides parsing, compare command."""

from __future__ import annotations

import argparse
import json

import allure
import pytest

from benchmarks.cli._compare import compare_command
from benchmarks.cli._jobs import _parse_judge_overrides


class _FakeWriter:
    """Accumulates stdout lines for assertion."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, line: str) -> None:
        self.lines.append(line)


def _write_report(path, *, scenario_id="memory", total_awarded=5, k_yes=2, awarded=3):
    payload = {
        "scenario_id": scenario_id,
        "iteration": 0,
        "total_awarded": total_awarded,
        "total_base": 10,
        "element_scores": [
            {
                "element_id": "e1",
                "label": "recall",
                "kind": "evidence_llm",
                "base_value": 3,
                "awarded": awarded,
                "k_yes": k_yes,
                "n_total": 3,
            },
            {
                "element_id": "e2",
                "label": "clock",
                "kind": "deterministic",
                "base_value": 1,
                "awarded": 1,
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


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
class TestCompareCommand:
    @allure.story("Compare command")
    @allure.title("compare_command prints baseline/current headers and a per-element delta table")
    def test_happy_path_prints_table(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        current = tmp_path / "current.json"
        _write_report(baseline, k_yes=1, awarded=1, total_awarded=2)
        _write_report(current, k_yes=3, awarded=3, total_awarded=4)
        args = argparse.Namespace(baseline=str(baseline), current=str(current))
        writer = _FakeWriter()

        exit_code = compare_command(args, writer=writer)

        assert exit_code == 0
        assert any("Baseline:" in line for line in writer.lines)
        assert any("Current" in line for line in writer.lines)
        # Delta column for evidence-LLM element: +2 points, 1→3 YES.
        delta_rows = [line for line in writer.lines if "recall" in line]
        assert delta_rows
        assert "+2" in delta_rows[0]
        assert "1→3 YES" in delta_rows[0]

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
        _write_report(good)
        args = argparse.Namespace(baseline=str(broken), current=str(good))

        with pytest.raises(ValueError, match="not valid JSON"):
            compare_command(args, writer=_FakeWriter())
