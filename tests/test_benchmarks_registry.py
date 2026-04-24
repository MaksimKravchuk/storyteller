"""Unit tests for :mod:`benchmarks.scenarios` — registry lookup semantics.

Smoke-level checks that the scenario registry is wired correctly:
:data:`ALL_SCENARIOS` contains both flagship scenarios, each has a
buildable state, and :func:`get_scenario` raises a clear ``KeyError`` on
typos.
"""

from __future__ import annotations

import allure
import pytest

from benchmarks.scenarios._registry import ALL_SCENARIOS, get_scenario


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestScenarioRegistry:
    @allure.story("Scenario registry")
    @allure.title("ALL_SCENARIOS exposes every flagship scenario with unique, stable ids")
    def test_registry_contains_flagship_scenarios(self):
        ids = {scenario.id for scenario in ALL_SCENARIOS}

        assert "memory_follow_up_marcus" in ids
        assert "memory_follow_up_marcus_graph_only" in ids
        assert "autonomy_three_guards_tavern" in ids
        assert "escalation_guard_assault" in ids
        assert len(ids) == len(ALL_SCENARIOS)  # no duplicates

    @allure.story("Scenario registry")
    @allure.title("get_scenario resolves each id back to the Scenario object registered in ALL_SCENARIOS")
    def test_get_scenario_resolves_by_id(self):
        for scenario in ALL_SCENARIOS:
            assert get_scenario(scenario.id) is scenario

    @allure.story("Scenario registry")
    @allure.title("get_scenario raises KeyError for unknown ids and lists the known ids in the message")
    def test_get_scenario_unknown_id_raises(self):
        with pytest.raises(KeyError) as excinfo:
            get_scenario("does_not_exist")

        assert "does_not_exist" in str(excinfo.value)
        assert "memory_follow_up_marcus" in str(excinfo.value)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestScenarioBuildState:
    @allure.story("Scenario state builder")
    @allure.title("Every registered scenario build_state() returns a fresh GameState with a current_scene and NPCs")
    def test_build_state_yields_usable_state(self):
        for scenario in ALL_SCENARIOS:
            state = scenario.build_state()

            assert state.game_state.current_scene is not None, scenario.id
            assert state.game_state.npcs, "{0} has no NPCs".format(scenario.id)

    @allure.story("Scenario state builder")
    @allure.title(
        "Two successive build_state calls return independent GameState objects so iterations never share state"
    )
    def test_build_state_is_idempotent(self):
        for scenario in ALL_SCENARIOS:
            first = scenario.build_state()
            second = scenario.build_state()

            # Different Python objects — mutating one cannot affect the other.
            assert first.game_state is not second.game_state
            assert first.game_state.npcs.keys() == second.game_state.npcs.keys()

    @allure.story("Scenario rubric")
    @allure.title("Every scenario declares a rubric whose element base_values sum to a positive integer")
    def test_rubric_has_positive_total(self):
        for scenario in ALL_SCENARIOS:
            total = sum(element.base_value for element in scenario.elements)

            assert total > 0, "{0} has a zero-sum rubric".format(scenario.id)
