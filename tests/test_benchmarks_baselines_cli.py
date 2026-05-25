"""Unit tests for the ``benchmarks baselines`` subcommand."""

from __future__ import annotations

import argparse

import allure

from benchmarks.cli._baselines import baselines_command
from benchmarks.harness import baselines
from benchmarks.harness.types._aggregates import ElementPassRate, PinnedBaseline, ScenarioAggregate


def _seed_baseline(scenario_id: str) -> None:
    aggregate = ScenarioAggregate(
        scenario_id=scenario_id,
        scenario_label=scenario_id,
        iterations=3,
        total_base=10,
        mean_awarded=7.0,
        min_awarded=6,
        max_awarded=8,
        element_pass_rates=[
            ElementPassRate(element_id="e1", label="recall", base_value=3, passes=2, iterations=3),
        ],
        iteration_totals=[6, 7, 8],
        stdev_awarded=0.8,
    )
    baselines.write_baseline(
        PinnedBaseline(
            aggregate=aggregate,
            baselined_at="2026-05-25T12:00:00+00:00",
            engine_git_sha="deadbee1",
            engine_models={},
            iterations=3,
            noise_floor_stdev=0.5,
        ),
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestBaselinesListCommand:
    @allure.story("Inspect baselines")
    @allure.title("baselines list prints one scenario id per pinned baseline")
    def test_list_prints_each_scenario(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        _seed_baseline("memory_follow_up_marcus")
        _seed_baseline("narrator_prose_quiet_exploration")

        exit_code = baselines_command(argparse.Namespace(baselines_action="list"))
        out = capsys.readouterr().out

        assert exit_code == 0
        assert "memory_follow_up_marcus" in out
        assert "narrator_prose_quiet_exploration" in out

    @allure.story("Inspect baselines")
    @allure.title("baselines list reports a sentinel when nothing is pinned")
    def test_list_empty_sentinel(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)

        exit_code = baselines_command(argparse.Namespace(baselines_action="list"))
        out = capsys.readouterr().out

        assert exit_code == 0
        assert "no baselines pinned" in out

    @allure.story("Inspect baselines")
    @allure.title("baselines rejects an unknown action with exit code 2")
    def test_unknown_action_exit_2(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)

        exit_code = baselines_command(argparse.Namespace(baselines_action="bogus"))
        err = capsys.readouterr().err

        assert exit_code == 2
        assert "Unknown baselines action" in err
