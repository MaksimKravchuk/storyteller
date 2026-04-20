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


class _FakeWriter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, line: str) -> None:
        self.lines.append(line)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestFinaliseAggregates:
    @allure.story("Run orchestration")
    @allure.title("interleaved scenarios group back into per-scenario aggregates in first-seen order")
    def test_interleaved_scenarios(self, tmp_path, monkeypatch):
        monkeypatch.setattr("benchmarks.harness.archive.results_dir", lambda: tmp_path)
        reports = [
            _report("s1", 0),
            _report("s2", 0),
            dataclasses.replace(_report("s1", 1), total_awarded=5),
            dataclasses.replace(_report("s2", 1), total_awarded=1),
        ]
        writer = _FakeWriter()

        aggregates = finalise_aggregates(reports, sha="cafe123", writer=writer)

        assert [agg.scenario_id for agg in aggregates] == ["s1", "s2"]
        assert all(agg.iterations == 2 for agg in aggregates)
        aggregate_lines = [line for line in writer.lines if "aggregate over" in line]
        assert len(aggregate_lines) == 2

    @allure.story("Run orchestration")
    @allure.title("empty input produces no aggregates and no writer output")
    def test_no_reports(self, tmp_path, monkeypatch):
        monkeypatch.setattr("benchmarks.harness.archive.results_dir", lambda: tmp_path)
        writer = _FakeWriter()

        aggregates = finalise_aggregates([], sha="cafe123", writer=writer)

        assert aggregates == []
        assert writer.lines == []
