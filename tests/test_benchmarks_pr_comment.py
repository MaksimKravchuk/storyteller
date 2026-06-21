"""Tests for the markdown ``benchmarks pr-comment`` subcommand and its formatter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import allure

from benchmarks.cli import _main, _pr_comment, _pr_comment_elements, _pr_comment_format, _pr_comment_rows
from benchmarks.cli._auto_compare import Verdict
from benchmarks.harness import baselines
from benchmarks.harness.bayes._report import verdict_for_scenario
from benchmarks.harness.types._aggregates import ElementPassRate, PinnedBaseline, ScenarioAggregate

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Benchmark harness"),
]


def _rate(element_id: str, *, passes: int, iterations: int, k_yes: int = 0, n_votes: int = 0) -> dict:
    return {
        "element_id": element_id,
        "label": element_id,
        "base_value": 2,
        "passes": passes,
        "iterations": iterations,
        "k_yes": k_yes,
        "n_votes": n_votes,
    }


def _aggregate_dict(*, scenario_id: str, mean: float, iterations: int, total: int, rates: list[dict]) -> dict:
    centre = int(round(mean))
    return {
        "scenario_id": scenario_id,
        "scenario_label": scenario_id,
        "iterations": iterations,
        "total_base": total,
        "mean_awarded": mean,
        "min_awarded": centre,
        "max_awarded": centre,
        "stdev_awarded": 1.0,
        "iteration_totals": [centre for _ in range(iterations)],
        "element_pass_rates": rates,
    }


def _write_aggregate(directory: Path, scenario_id: str, payload: dict) -> None:
    path = directory / "{0}_aggregate.json".format(scenario_id)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_iteration(directory: Path, scenario_id: str, narration: str) -> None:
    payload = {
        "scenario_id": scenario_id,
        "iteration": 0,
        "captured_turns": [{"index": 0, "player_action": "look", "narration": narration}],
    }
    (directory / "{0}_iter0.json".format(scenario_id)).write_text(json.dumps(payload), encoding="utf-8")


def _pin_baseline(scenario_id: str, *, mean: float, noise: float, rates: list[ElementPassRate]) -> None:
    centre = int(round(mean))
    aggregate = ScenarioAggregate(
        scenario_id=scenario_id,
        scenario_label=scenario_id,
        iterations=3,
        total_base=10,
        mean_awarded=mean,
        min_awarded=centre,
        max_awarded=centre,
        element_pass_rates=rates,
        iteration_totals=[centre, centre, centre],
        stdev_awarded=noise,
    )
    baselines.write_baseline(
        PinnedBaseline(
            aggregate=aggregate,
            baselined_at="2026-06-20T00:00:00+00:00",
            engine_git_sha="cafef00d",
            engine_models={},
            iterations=3,
            noise_floor_stdev=noise,
        ),
    )


def _verdict(scenario_id: str, classification: str, *, base: float = 8.0, cur: float = 8.0) -> Verdict:
    return Verdict(
        scenario_id=scenario_id,
        classification=classification,  # type: ignore[arg-type]
        baseline_mean=base,
        current_mean=cur,
        delta_vs_noise_floor=cur - base,
    )


@allure.story("PR comment")
class TestHeadlineBadge:
    @allure.title("a regression anywhere flips the badge to red")
    def test_regression_wins(self):
        verdicts = [_verdict("a", "noise"), _verdict("b", "regression")]

        assert "🔴 Regression detected" in _pr_comment_format.format_headline(verdicts)

    @allure.title("all-noise scenarios read as no regression")
    def test_clean(self):
        assert "✅ No regression" in _pr_comment_format.format_headline([_verdict("a", "noise")])

    @allure.title("improvement without regression reads as improvement")
    def test_improvement(self):
        verdicts = [_verdict("a", "noise"), _verdict("b", "improvement")]

        assert "🟢 Improvement" in _pr_comment_format.format_headline(verdicts)

    @allure.title("only unpinned scenarios read as no pinned baselines")
    def test_no_baseline(self):
        assert "⚪ No pinned baselines yet" in _pr_comment_format.format_headline([_verdict("a", "no_baseline")])

    @allure.title("no scenarios at all reads as no results")
    def test_empty(self):
        assert "⚪ No results produced" in _pr_comment_format.format_headline([])


@allure.story("PR comment")
class TestSummaryTable:
    @allure.title("a pinned scenario renders mean transition, noise-floor delta, and verdict marker")
    def test_pinned_row(self):
        summary = _pr_comment_rows.ScenarioSummary(verdict=_verdict("marcus", "noise", base=8.5, cur=8.4), bayes=None)

        table = _pr_comment_rows.format_summary_table([summary])

        assert "| marcus | 8.50 → 8.40 | -0.10σ | — | ✅ noise |" in table

    @allure.title("an unpinned scenario blanks the baseline mean and floor cells")
    def test_no_baseline_row(self):
        summary = _pr_comment_rows.ScenarioSummary(
            verdict=_verdict("orphan", "no_baseline", base=float(0), cur=9.0), bayes=None
        )

        table = _pr_comment_rows.format_summary_table([summary])

        assert "| orphan | — → 9.00 | — | — | ⚪ no baseline |" in table

    @allure.title("an empty summary degrades to a placeholder")
    def test_empty(self):
        assert "_No scenarios scored" in _pr_comment_rows.format_summary_table([])


@allure.story("PR comment")
class TestPortfolioLine:
    @allure.title("no portfolio degrades to a placeholder")
    def test_none(self):
        assert "_No pinned baselines to pool" in _pr_comment_format.format_portfolio(None)


@allure.story("PR comment")
class TestElementsSection:
    @allure.title("a notable per-element move surfaces in the collapsible section")
    def test_notable_element_listed(self):
        baseline = _aggregate_dict(
            scenario_id="s1",
            mean=10.0,
            iterations=3,
            total=10,
            rates=[_rate("persona", passes=3, iterations=3)],
        )
        current = _aggregate_dict(
            scenario_id="s1",
            mean=6.0,
            iterations=1,
            total=10,
            rates=[_rate("persona", passes=0, iterations=1)],
        )
        bayes = verdict_for_scenario(baseline, current, noise_floor_stdev=0.5)
        summary = _pr_comment_rows.ScenarioSummary(verdict=_verdict("s1", "regression"), bayes=bayes)

        section = _pr_comment_elements.format_elements_section([summary])

        assert "<details><summary>📊 Per-element deltas</summary>" in section
        assert "#### s1" in section
        assert "| persona |" in section

    @allure.title("no notable moves degrade to a placeholder inside the section")
    def test_no_notable(self):
        section = _pr_comment_elements.format_elements_section([])

        assert "_No notable per-element movements" in section


@allure.story("PR comment")
class TestPrCommentCommand:
    @allure.title("command renders headline, table, portfolio, and narration against a pinned baseline")
    def test_full_comment(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path / "baselines")
        (tmp_path / "baselines").mkdir()
        results = tmp_path / "results"
        results.mkdir()
        _pin_baseline("marcus", mean=8.0, noise=1.0, rates=[])
        _write_aggregate(
            results, "marcus", _aggregate_dict(scenario_id="marcus", mean=8.0, iterations=1, total=10, rates=[])
        )
        _write_iteration(results, "marcus", "fresh prose")

        exit_code = _pr_comment.pr_comment_command(
            argparse.Namespace(results=str(results), previous="", rope=None),
        )

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "## 🎭 Benchmark comparison" in out
        assert "| marcus |" in out
        assert "**Portfolio (1 scenarios):**" in out
        assert "## 📖 Narration diff" in out
        assert "❓ How to read this" in out

    @allure.title("an unpinned scenario yields the no-baseline badge and blanked cells")
    def test_unpinned_scenario(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path / "baselines")
        results = tmp_path / "results"
        results.mkdir()
        _write_aggregate(
            results, "orphan", _aggregate_dict(scenario_id="orphan", mean=9.0, iterations=1, total=10, rates=[])
        )

        exit_code = _pr_comment.pr_comment_command(
            argparse.Namespace(results=str(results), previous="", rope=None),
        )

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "⚪ No pinned baselines yet" in out
        assert "| orphan | — → 9.00 | — | — | ⚪ no baseline |" in out
        assert "_No pinned baselines to pool" in out

    @allure.title("a missing results directory exits 1")
    def test_missing_results_dir(self, tmp_path, capsys):
        exit_code = _pr_comment.pr_comment_command(
            argparse.Namespace(results=str(tmp_path / "nope"), previous="", rope=None),
        )

        assert exit_code == 1
        assert "Results directory not found" in capsys.readouterr().err

    @allure.title("the narration diff compares against the previous-main directory")
    def test_narration_against_previous(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path / "baselines")
        results = tmp_path / "results"
        previous = tmp_path / "prev"
        results.mkdir()
        previous.mkdir()
        _write_aggregate(
            results, "marcus", _aggregate_dict(scenario_id="marcus", mean=8.0, iterations=1, total=10, rates=[])
        )
        _write_iteration(results, "marcus", "new prose")
        _write_iteration(previous, "marcus", "old prose")

        exit_code = _main.main(["pr-comment", str(results), "--previous", str(previous)])

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "> old prose" in out
        assert "> new prose" in out
