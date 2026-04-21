"""Tests for WAIT action type, keyword detection, and forced wait."""

from __future__ import annotations

import allure

from cast.wait_detection import (
    INCAPACITATING_STATES,
    build_forced_wait_plan,
    detect_wait_intent,
    is_incapacitated,
)


@allure.epic("Game Timeline")
@allure.feature("Wait intent detection")
class TestDetectWaitIntentEnglish:
    """English wait keyword detection."""

    @allure.story("English keywords")
    @allure.title("The '/wait' slash command is detected as a wait intent")
    def test_slash_wait_command(self):
        assert detect_wait_intent("/wait") is True

    @allure.story("English keywords")
    @allure.title("The bare word 'wait' is detected as a wait intent")
    def test_plain_wait(self):
        assert detect_wait_intent("wait") is True

    @allure.story("English keywords")
    @allure.title("The phrase 'I wait' is detected as a wait intent")
    def test_i_wait(self):
        assert detect_wait_intent("I wait") is True

    @allure.story("English keywords")
    @allure.title("The phrase 'do nothing' is detected as a wait intent")
    def test_do_nothing(self):
        assert detect_wait_intent("do nothing") is True

    @allure.story("English keywords")
    @allure.title("The bare word 'pass' is detected as a wait intent")
    def test_pass_turn(self):
        assert detect_wait_intent("pass") is True

    @allure.story("English keywords")
    @allure.title("The phrase 'skip turn' is detected as a wait intent")
    def test_skip_turn(self):
        assert detect_wait_intent("skip turn") is True

    @allure.story("English keywords")
    @allure.title("'I wait for the merchant' is not a wait because the phrase has a target object")
    def test_wait_with_target_not_detected(self):
        """'I wait for the merchant' is NOT a wait — it has a target."""
        assert detect_wait_intent("I wait for the merchant") is False

    @allure.story("English keywords")
    @allure.title("A normal attack action like 'I attack the guard' is not detected as a wait")
    def test_normal_action_not_detected(self):
        assert detect_wait_intent("I attack the guard") is False

    @allure.story("English keywords")
    @allure.title("An exploration action like 'look around' is not detected as a wait")
    def test_explore_not_detected(self):
        assert detect_wait_intent("look around") is False

    @allure.story("English keywords")
    @allure.title("Wait keyword detection is case-insensitive")
    def test_case_insensitive(self):
        assert detect_wait_intent("WAIT") is True
        assert detect_wait_intent("I WAIT") is True

    @allure.story("English keywords")
    @allure.title("The variant 'I do nothing' is detected as a wait intent")
    def test_do_nothing_variant(self):
        assert detect_wait_intent("I do nothing") is True

    @allure.story("English keywords")
    @allure.title("The phrase 'stand still' is detected as a wait intent")
    def test_stand_still(self):
        assert detect_wait_intent("stand still") is True


@allure.epic("Game Timeline")
@allure.feature("Wait intent detection")
class TestDetectWaitIntentRussian:
    """Russian wait keyword detection."""

    @allure.story("Russian keywords")
    @allure.title("The Russian verb 'жду' (I wait) is detected as a wait intent when language is Russian")
    def test_zhdu(self):
        assert detect_wait_intent("жду", language="Russian") is True

    @allure.story("Russian keywords")
    @allure.title("The Russian word 'пас' (pass) is detected as a wait intent")
    def test_pas(self):
        assert detect_wait_intent("пас", language="Russian") is True

    @allure.story("Russian keywords")
    @allure.title("The Russian phrase 'ничего не делаю' (I do nothing) is detected as a wait intent")
    def test_nichego_ne_delayu(self):
        assert detect_wait_intent("ничего не делаю", language="Russian") is True

    @allure.story("Russian keywords")
    @allure.title("The Russian phrase 'пропускаю ход' (I skip turn) is detected as a wait intent")
    def test_propuskayu_hod(self):
        assert detect_wait_intent("пропускаю ход", language="Russian") is True

    @allure.story("Russian keywords")
    @allure.title("A Russian attack action is not mistakenly detected as a wait intent")
    def test_normal_action_russian(self):
        assert detect_wait_intent("атакую стражника", language="Russian") is False


@allure.epic("Game Timeline")
@allure.feature("Wait intent detection")
class TestIsIncapacitated:
    """Player state incapacitation check."""

    @allure.story("Incapacitation")
    @allure.title("A 'healthy' physical status is not considered incapacitated")
    def test_healthy_not_incapacitated(self):
        assert is_incapacitated("healthy") is False

    @allure.story("Incapacitation")
    @allure.title("An 'unconscious' physical status marks the player as incapacitated")
    def test_unconscious_is_incapacitated(self):
        assert is_incapacitated("unconscious") is True

    @allure.story("Incapacitation")
    @allure.title("A 'stunned' physical status marks the player as incapacitated")
    def test_stunned_is_incapacitated(self):
        assert is_incapacitated("stunned") is True

    @allure.story("Incapacitation")
    @allure.title("A 'tied up' physical status marks the player as incapacitated")
    def test_tied_up_is_incapacitated(self):
        assert is_incapacitated("tied up") is True

    @allure.story("Incapacitation")
    @allure.title("A 'frightened' physical status marks the player as incapacitated")
    def test_frightened_is_incapacitated(self):
        assert is_incapacitated("frightened") is True

    @allure.story("Incapacitation")
    @allure.title("A 'frozen' physical status marks the player as incapacitated")
    def test_frozen_is_incapacitated(self):
        assert is_incapacitated("frozen") is True

    @allure.story("Incapacitation")
    @allure.title("A 'wounded' player can still act and is not considered incapacitated")
    def test_wounded_not_incapacitated(self):
        assert is_incapacitated("wounded") is False

    @allure.story("Incapacitation")
    @allure.title("Incapacitation checks are case-insensitive across status string values")
    def test_case_insensitive(self):
        assert is_incapacitated("UNCONSCIOUS") is True
        assert is_incapacitated("Stunned") is True

    @allure.story("Incapacitation")
    @allure.title("The INCAPACITATING_STATES constant is an immutable frozenset")
    def test_incapacitating_states_is_frozenset(self):
        assert isinstance(INCAPACITATING_STATES, frozenset)


@allure.epic("Game Timeline")
@allure.feature("Wait intent detection")
class TestBuildForcedWaitPlan:
    """Forced wait produces a valid WaitPlan."""

    @allure.story("Forced wait plan")
    @allure.title("A forced wait plan has action_type set to 'WAIT'")
    def test_action_type_is_wait(self):
        plan = build_forced_wait_plan("unconscious")
        assert plan.action_type == "WAIT"

    @allure.story("Forced wait plan")
    @allure.title("A forced wait plan delegates narration directly to the narrator")
    def test_delegates_to_narrator(self):
        plan = build_forced_wait_plan("stunned")
        assert plan.delegate_to == ["narrator"]

    @allure.story("Forced wait plan")
    @allure.title("A forced wait plan carries a human-readable intent string")
    def test_carries_intent(self):
        plan = build_forced_wait_plan("tied up")
        assert "tied up" in plan.intent

    @allure.story("Forced wait plan")
    @allure.title("A forced wait plan does not override the default time cost")
    def test_no_time_cost_override(self):
        plan = build_forced_wait_plan("frightened")
        assert plan.time_cost_override is None

    @allure.story("Forced wait plan")
    @allure.title("A forced wait plan records the incapacitation reason in its wait_reason field")
    def test_has_reason(self):
        plan = build_forced_wait_plan("unconscious")
        assert plan.wait_reason == "unconscious"


@allure.epic("Game Timeline")
@allure.feature("Wait intent detection")
class TestWaitInActionTypes:
    """WAIT is properly registered in the action system."""

    @allure.story("Action system registration")
    @allure.title("WAIT appears in the TURN_COUNTING_ACTIONS set so it advances the turn count")
    def test_wait_in_turn_counting_actions(self):
        from cast.constants import TURN_COUNTING_ACTIONS

        assert "WAIT" in TURN_COUNTING_ACTIONS

    @allure.story("Action system registration")
    @allure.title("WAIT has a positive entry in BASE_ACTION_COSTS so it costs real game time")
    def test_wait_has_time_cost(self):
        from timeline.time_costs import BASE_ACTION_COSTS

        assert "WAIT" in BASE_ACTION_COSTS
        assert BASE_ACTION_COSTS["WAIT"] > 0
