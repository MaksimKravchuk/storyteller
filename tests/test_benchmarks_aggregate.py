"""Unit tests for cross-iteration aggregation of scenario reports."""

from __future__ import annotations

import dataclasses
import json

import allure
import pytest

from benchmarks.harness.aggregate import aggregate_reports, element_passed
from benchmarks.harness.aggregate_archive import write_aggregate
from benchmarks.harness.types._aggregates import ElementPassRate, ScenarioAggregate
from benchmarks.harness.types._elements import KIND_DETERMINISTIC, KIND_EVIDENCE_LLM
from benchmarks.harness.types._scores import ElementScore, ScenarioReport


def _element(element_id: str, *, base: int, awarded: int, kind=KIND_DETERMINISTIC) -> ElementScore:
    """Build a minimal :class:`ElementScore` for aggregation tests."""
    return ElementScore(
        element_id=element_id,
        label=element_id,
        kind=kind,
        base_value=base,
        awarded=awarded,
    )


def _report(*, iteration: int, awarded: int, element_scores: list[ElementScore]) -> ScenarioReport:
    """Build a minimal :class:`ScenarioReport` for aggregation tests."""
    return ScenarioReport(
        scenario_id="s1",
        scenario_label="s1",
        iteration=iteration,
        total_base=5,
        total_awarded=awarded,
        element_scores=element_scores,
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
class TestElementPassed:
    @allure.story("Aggregation")
    @allure.title("element_passed is True when awarded is at least half of base (majority credit)")
    def test_majority_credit_passes(self):
        assert element_passed(_element("e1", base=3, awarded=3))
        assert element_passed(_element("e1", base=3, awarded=2))
        assert not element_passed(_element("e1", base=3, awarded=1))
        assert not element_passed(_element("e1", base=3, awarded=0))

    @allure.story("Aggregation")
    @allure.title("element_passed is False for zero-base elements so degenerate cases cannot inflate rates")
    def test_zero_base_never_passes(self):
        assert not element_passed(_element("e1", base=0, awarded=0))


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestAggregateReports:
    @allure.story("Aggregation")
    @allure.title("aggregate_reports computes mean, min, and max across iteration totals")
    def test_mean_min_max(self):
        reports = [
            _report(iteration=0, awarded=3, element_scores=[_element("e1", base=5, awarded=3)]),
            _report(iteration=1, awarded=5, element_scores=[_element("e1", base=5, awarded=5)]),
            _report(iteration=2, awarded=4, element_scores=[_element("e1", base=5, awarded=4)]),
        ]

        result = aggregate_reports(reports)

        assert result.iterations == 3
        assert result.mean_awarded == pytest.approx(4.0)
        assert result.min_awarded == 3
        assert result.max_awarded == 5
        assert result.iteration_totals == [3, 5, 4]

    @allure.story("Aggregation")
    @allure.title("aggregate_reports reports per-element pass rates in first-seen element order")
    def test_element_pass_rates(self):
        reports = [
            _report(
                iteration=0,
                awarded=5,
                element_scores=[
                    _element("a", base=3, awarded=3),
                    _element("b", base=2, awarded=0, kind=KIND_EVIDENCE_LLM),
                ],
            ),
            _report(
                iteration=1,
                awarded=5,
                element_scores=[
                    _element("a", base=3, awarded=1),
                    _element("b", base=2, awarded=2, kind=KIND_EVIDENCE_LLM),
                ],
            ),
        ]

        result = aggregate_reports(reports)

        rates = {rate.element_id: rate for rate in result.element_pass_rates}
        assert list(rates) == ["a", "b"]
        assert rates["a"].passes == 1
        assert rates["a"].iterations == 2
        assert rates["b"].passes == 1

    @allure.story("Aggregation")
    @allure.title("aggregate_reports rejects empty input so callers cannot silently produce a nonsensical summary")
    def test_empty_reports_raise(self):
        with pytest.raises(ValueError, match="at least one report"):
            aggregate_reports([])

    @allure.story("Aggregation")
    @allure.title("aggregate_reports rejects mixed scenario ids so callers cannot conflate unrelated runs")
    def test_mixed_scenarios_raise(self):
        first = _report(iteration=0, awarded=3, element_scores=[])
        second = dataclasses.replace(
            _report(iteration=1, awarded=3, element_scores=[]),
            scenario_id="s2",
        )

        with pytest.raises(ValueError, match="one scenario"):
            aggregate_reports([first, second])


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestWriteAggregate:
    @allure.story("Archive")
    @allure.title("write_aggregate emits both a JSON + markdown artefact and persists the core fields")
    def test_writes_json_and_markdown(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "benchmarks.harness.archive.results_dir",
            lambda: tmp_path,
        )
        aggregate = ScenarioAggregate(
            scenario_id="s1",
            scenario_label="Scenario One",
            iterations=3,
            total_base=5,
            mean_awarded=4.0,
            min_awarded=3,
            max_awarded=5,
            element_pass_rates=[
                ElementPassRate(element_id="e1", label="recall", base_value=3, passes=2, iterations=3),
            ],
            iteration_totals=[3, 4, 5],
        )

        json_path, md_path = write_aggregate(aggregate, "deadbee1")

        assert json_path.exists()
        assert md_path.exists()
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["scenario_id"] == "s1"
        assert payload["mean_awarded"] == pytest.approx(4.0)
        assert payload["engine_git_sha"] == "deadbee1"
        md_content = md_path.read_text(encoding="utf-8")
        assert "Scenario One" in md_content
        assert "recall" in md_content
