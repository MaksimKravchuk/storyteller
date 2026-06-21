"""Tests for the Bayesian compare formatting + the offline ``bayes-report`` command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import allure

from benchmarks.cli import _bayes_format, _compare
from benchmarks.cli._bayes_report import bayes_report_command
from benchmarks.harness import baselines
from benchmarks.harness.types._aggregates import (
    ElementPassRate,
    PinnedBaseline,
    ScenarioAggregate,
)


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


def _write_aggregate(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


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


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestBayesFormat:
    @allure.story("Bayesian compare")
    @allure.title("scenario line carries the delta, credible interval, and three probabilities")
    def test_scenario_line(self):
        from benchmarks.harness.bayes._report import verdict_for_scenario

        baseline = _aggregate_dict(scenario_id="s1", mean=10.0, iterations=3, total=10, rates=[])
        current = _aggregate_dict(scenario_id="s1", mean=6.0, iterations=3, total=10, rates=[])
        verdict = verdict_for_scenario(baseline, current, noise_floor_stdev=0.5)

        line = _bayes_format.format_scenario_line(verdict)

        assert line.startswith("[bayes] s1:")
        assert "Δ=-4.00" in line
        assert "P(reg)=" in line and "P(eq)=" in line and "P(imp)=" in line

    @allure.story("Bayesian compare")
    @allure.title("scenario block appends notable per-element rows above the confidence threshold")
    def test_scenario_block_surfaces_notable_elements(self):
        from benchmarks.harness.bayes._report import verdict_for_scenario

        rates_base = [_rate("strong", passes=3, iterations=3), _rate("quiet", passes=2, iterations=3)]
        rates_cur = [_rate("strong", passes=0, iterations=1), _rate("quiet", passes=1, iterations=1)]
        baseline = _aggregate_dict(scenario_id="s1", mean=10.0, iterations=3, total=10, rates=rates_base)
        current = _aggregate_dict(scenario_id="s1", mean=6.0, iterations=1, total=10, rates=rates_cur)
        verdict = verdict_for_scenario(baseline, current, noise_floor_stdev=0.5)

        block = _bayes_format.format_scenario_block(verdict)

        assert block[0].startswith("[bayes] s1:")
        assert any("strong" in row for row in block[1:])


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestBayesReportCommand:
    @allure.story("Bayesian compare")
    @allure.title("bayes-report prints a graded verdict per scenario plus a pooled portfolio line")
    def test_reports_scenarios_and_portfolio(self, tmp_path, monkeypatch, capsys):
        baselines_path = tmp_path / "baselines"
        baselines_path.mkdir()
        monkeypatch.setattr(baselines, "baselines_dir", lambda: baselines_path)
        results = tmp_path / "results"
        results.mkdir()
        for idx in range(3):
            scenario = "s{0}".format(idx)
            _pin_baseline(scenario, mean=10.0, noise=1.0, rates=[])
            _write_aggregate(
                results / "{0}_aggregate.json".format(scenario),
                _aggregate_dict(scenario_id=scenario, mean=9.0, iterations=1, total=10, rates=[]),
            )

        exit_code = bayes_report_command(argparse.Namespace(results=str(results), rope=None))

        out = capsys.readouterr().out
        assert exit_code == 0
        assert out.count("[bayes] s") == 3
        assert "PORTFOLIO (3 scenarios)" in out
        assert "P(suite worse)=" in out

    @allure.story("Bayesian compare")
    @allure.title("bayes-report counts each scenario once when the archive holds duplicate aggregates")
    def test_deduplicates_archive_history(self, tmp_path, monkeypatch, capsys):
        baselines_path = tmp_path / "baselines"
        baselines_path.mkdir()
        monkeypatch.setattr(baselines, "baselines_dir", lambda: baselines_path)
        results = tmp_path / "results"
        results.mkdir()
        _pin_baseline("s0", mean=10.0, noise=1.0, rates=[])
        # Two historical aggregate files for the SAME scenario — must not double-count.
        _write_aggregate(
            results / "2026-01-01T00-00-00_aaa_s0_aggregate.json",
            _aggregate_dict(scenario_id="s0", mean=9.0, iterations=1, total=10, rates=[]),
        )
        _write_aggregate(
            results / "2026-02-02T00-00-00_bbb_s0_aggregate.json",
            _aggregate_dict(scenario_id="s0", mean=8.0, iterations=1, total=10, rates=[]),
        )

        exit_code = bayes_report_command(argparse.Namespace(results=str(results), rope=None))

        out = capsys.readouterr().out
        assert exit_code == 0
        assert out.count("[bayes] s0:") == 1
        assert "PORTFOLIO (1 scenarios)" in out

    @allure.story("Bayesian compare")
    @allure.title("bayes-report skips scenarios with no pinned baseline")
    def test_skips_unpinned(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path / "baselines")
        results = tmp_path / "results"
        results.mkdir()
        _write_aggregate(
            results / "orphan_aggregate.json",
            _aggregate_dict(scenario_id="orphan", mean=9.0, iterations=1, total=10, rates=[]),
        )

        exit_code = bayes_report_command(argparse.Namespace(results=str(results), rope=None))

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "no pinned baseline — skipped" in out
        assert "PORTFOLIO" not in out

    @allure.story("Bayesian compare")
    @allure.title("bayes-report returns 1 when the results directory is missing")
    def test_missing_results_dir(self, tmp_path, capsys):
        exit_code = bayes_report_command(
            argparse.Namespace(results=str(tmp_path / "nope"), rope=None),
        )

        assert exit_code == 1
        assert "Results directory not found" in capsys.readouterr().err


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestCompareAugmentation:
    @allure.story("Bayesian compare")
    @allure.title("compare prints a graded Bayesian line beneath the frequentist banner")
    def test_compare_emits_bayes_line(self, tmp_path, capsys):
        baseline_path = tmp_path / "base_aggregate.json"
        current_path = tmp_path / "cur_aggregate.json"
        _write_aggregate(
            baseline_path,
            _aggregate_dict(scenario_id="s1", mean=10.0, iterations=3, total=10, rates=[]),
        )
        _write_aggregate(
            current_path,
            _aggregate_dict(scenario_id="s1", mean=6.0, iterations=1, total=10, rates=[]),
        )

        exit_code = _compare.compare_command(
            argparse.Namespace(baseline=str(baseline_path), current=str(current_path)),
        )

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "[bayes] s1:" in out
        assert "Scenario verdict:" in out  # frequentist banner still present
