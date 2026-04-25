"""Filename-pattern matching for the cross-set comparison report."""

from __future__ import annotations

import allure
import pytest

from benchmarks.model_sets import _patterns

_BASELINE_AGG = "2026-04-24T22-23-37_3d6410b_memory_follow_up_marcus_aggregate.json"
_BASELINE_AGG_GRAPH_ONLY = "2026-04-24T22-26-43_3d6410b_memory_follow_up_marcus_graph_only_aggregate.json"
_SET_AGG = "set-economy__2026-04-24T22-23-37_3d6410b_memory_follow_up_marcus_aggregate.json"
_SET_AGG_GRAPH_ONLY = "set-max__2026-04-24T22-15-10_3d6410b_memory_follow_up_marcus_graph_only_aggregate.json"
_SET_ITER0 = "set-economy__2026-04-24T22-20-09_3d6410b_memory_follow_up_marcus_iter0.json"
_SET_ITER12 = "set-economy__2026-04-24T22-20-09_3d6410b_memory_follow_up_marcus_iter12.json"


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark model-set comparison")
class TestIsBaselineAggregate:
    @allure.story("Baseline detection")
    @allure.title("Untagged aggregate filenames are recognised as baseline")
    @pytest.mark.parametrize("name", [_BASELINE_AGG, _BASELINE_AGG_GRAPH_ONLY])
    def test_accepts_untagged_aggregate(self, name: str) -> None:
        scenario = "memory_follow_up_marcus_graph_only" if "graph_only" in name else "memory_follow_up_marcus"
        assert _patterns.is_baseline_aggregate(name, scenario) is True

    @allure.story("Baseline detection")
    @allure.title("Set-tagged filenames are not treated as baseline")
    @pytest.mark.parametrize("name", [_SET_AGG, _SET_ITER0])
    def test_rejects_set_tagged(self, name: str) -> None:
        assert _patterns.is_baseline_aggregate(name, "memory_follow_up_marcus") is False

    @allure.story("Scenario-id collision safety")
    @allure.title("Querying `marcus` does not match the `marcus_graph_only` aggregate")
    def test_rejects_scenario_id_substring_collision(self) -> None:
        assert _patterns.is_baseline_aggregate(_BASELINE_AGG_GRAPH_ONLY, "memory_follow_up_marcus") is False


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark model-set comparison")
class TestIsSetAggregate:
    @allure.story("Set-aggregate matching")
    @allure.title("Matches the per-set aggregate for the named set and scenario")
    def test_matches_for_named_set(self) -> None:
        assert _patterns.is_set_aggregate(_SET_AGG, "economy", "memory_follow_up_marcus") is True

    @allure.story("Set-aggregate matching")
    @allure.title("Baseline aggregates are rejected for any named set")
    def test_rejects_baseline(self) -> None:
        assert _patterns.is_set_aggregate(_BASELINE_AGG, "economy", "memory_follow_up_marcus") is False

    @allure.story("Scenario-id collision safety")
    @allure.title("Querying `marcus` does not match the `marcus_graph_only` set aggregate")
    def test_rejects_scenario_id_substring_collision(self) -> None:
        assert _patterns.is_set_aggregate(_SET_AGG_GRAPH_ONLY, "max", "memory_follow_up_marcus") is False

    @allure.story("Set-aggregate matching")
    @allure.title("A set's aggregate does not match a different set name")
    def test_rejects_other_set(self) -> None:
        assert _patterns.is_set_aggregate(_SET_AGG, "max", "memory_follow_up_marcus") is False


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark model-set comparison")
class TestIsSetIter:
    @allure.story("Iteration matching")
    @allure.title("Iteration files match for both single-digit and multi-digit indices")
    @pytest.mark.parametrize("name", [_SET_ITER0, _SET_ITER12])
    def test_matches_single_and_multi_digit(self, name: str) -> None:
        assert _patterns.is_set_iter(name, "economy", "memory_follow_up_marcus") is True

    @allure.story("Iteration matching")
    @allure.title("Aggregate filenames are not classified as iteration files")
    def test_rejects_aggregate(self) -> None:
        assert _patterns.is_set_iter(_SET_AGG, "economy", "memory_follow_up_marcus") is False
