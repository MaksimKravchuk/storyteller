"""Tests for the per-scenario grouping + archival flow."""

from __future__ import annotations

import dataclasses

import allure

from benchmarks.cli._aggregate_flow import finalise_aggregates
from benchmarks.harness.types._scores import ScenarioReport


def _report(scenario_id: str, iteration: int) -> ScenarioReport:
    return ScenarioReport(
        scenario_id=scenario_id,
        scenario_label=scenario_id,
        iteration=iteration,
        total_base=5,
        total_awarded=3,
        element_scores=[],
        captured_turns=[],
        panel=[],
        skipped_panel_candidates=[],
        engine_git_sha="abcdef1",
        engine_models={},
        started_at="2026-04-20T00:00:00+00:00",
        duration_seconds=1.0,
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestFinaliseAggregates:
    @allure.story("Run orchestration")
    @allure.title("interleaved scenarios group back into per-scenario aggregates in first-seen order")
    def test_interleaved_scenarios(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("benchmarks.harness.archive.results_dir", lambda: tmp_path)
        reports = [
            _report("s1", 0),
            _report("s2", 0),
            dataclasses.replace(_report("s1", 1), total_awarded=5),
            dataclasses.replace(_report("s2", 1), total_awarded=1),
        ]

        aggregates = finalise_aggregates(reports, sha="cafe123")

        assert [agg.scenario_id for agg in aggregates] == ["s1", "s2"]
        assert all(agg.iterations == 2 for agg in aggregates)
        out = capsys.readouterr().out
        assert out.count("aggregate over") == 2

    @allure.story("Run orchestration")
    @allure.title("empty input produces no aggregates and no output")
    def test_no_reports(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("benchmarks.harness.archive.results_dir", lambda: tmp_path)

        aggregates = finalise_aggregates([], sha="cafe123")

        assert aggregates == []
        assert capsys.readouterr().out == ""

    @allure.story("Run orchestration")
    @allure.title("engine_models from the per-iteration reports is propagated into the aggregate JSON")
    def test_engine_models_propagated(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setattr("benchmarks.harness.archive.results_dir", lambda: tmp_path)
        first = dataclasses.replace(
            _report("s1", 0),
            engine_models={"director_model": "gpt-5.4-mini", "narrator_model": "gpt-5.4-mini"},
        )
        second = dataclasses.replace(
            _report("s1", 1),
            engine_models={"director_model": "gpt-5.4-mini", "narrator_model": "gpt-5.4-mini"},
        )

        finalise_aggregates([first, second], sha="cafe123")

        json_files = sorted(tmp_path.glob("*_aggregate.json"))
        assert json_files, "expected an aggregate JSON in tmp_path"
        payload = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert payload["engine_models"] == {
            "director_model": "gpt-5.4-mini",
            "narrator_model": "gpt-5.4-mini",
        }
