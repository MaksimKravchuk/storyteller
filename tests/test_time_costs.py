"""Tests for the hybrid time-cost resolver.

``resolve_time_cost`` is exercised indirectly through Director routing,
but its two decision points — the ``llm_override is not None and > 0``
guard and the ``BASE_ACTION_COSTS.get(action.upper(), OTHER)`` fallback —
were never asserted in isolation. These pin both.
"""

from __future__ import annotations

import allure

from timeline.time_costs import BASE_ACTION_COSTS, resolve_time_cost

_OVERRIDE = 0.5


@allure.epic("Game Timeline")
@allure.feature("Time-cost resolution")
class TestLlmOverride:
    @allure.story("Override guard")
    @allure.title("A positive llm_override is returned verbatim, bypassing the base cost")
    def test_positive_override_wins(self):
        # Distinguishes `> 0` from `> 1`: 0.5 must still count as a valid override.
        assert resolve_time_cost("TALK", llm_override=_OVERRIDE) == _OVERRIDE

    @allure.story("Override guard")
    @allure.title("A zero llm_override is rejected and the base cost is used instead")
    def test_zero_override_falls_back_to_base(self):
        # Distinguishes `> 0` from `>= 0`: zero is not a usable override.
        assert resolve_time_cost("TALK", llm_override=0) == BASE_ACTION_COSTS["TALK"]

    @allure.story("Override guard")
    @allure.title("Omitting llm_override resolves to the base cost for the action type")
    def test_no_override_uses_base(self):
        assert resolve_time_cost("SLEEP") == BASE_ACTION_COSTS["SLEEP"]


@allure.epic("Game Timeline")
@allure.feature("Time-cost resolution")
class TestBaseCostLookup:
    @allure.story("Base lookup")
    @allure.title("A known action type maps to its specific base cost, not the OTHER fallback")
    def test_known_action_uses_its_own_cost(self):
        # Distinguishes `.get(action.upper(), OTHER)` from `.get(None, OTHER)`:
        # TALK (0.05) must not collapse to OTHER (0.02).
        assert resolve_time_cost("TALK") == BASE_ACTION_COSTS["TALK"]
        assert resolve_time_cost("TALK") != BASE_ACTION_COSTS["OTHER"]

    @allure.story("Base lookup")
    @allure.title("Action types are upper-cased before lookup, so lowercase input still resolves")
    def test_lookup_is_case_insensitive(self):
        # Distinguishes `.upper()` from `.lower()`: lowercase "talk" must hit TALK.
        assert resolve_time_cost("talk") == BASE_ACTION_COSTS["TALK"]

    @allure.story("Base lookup")
    @allure.title("An unknown action type falls back to the OTHER base cost rather than None")
    def test_unknown_action_falls_back_to_other(self):
        # Distinguishes `.get(key, OTHER)` from `.get(key, None)` / `.get(key)`.
        assert resolve_time_cost("DEFENESTRATE") == BASE_ACTION_COSTS["OTHER"]
