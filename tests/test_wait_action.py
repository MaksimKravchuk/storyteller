"""Tests for WAIT action type, keyword detection, and forced wait."""

from __future__ import annotations

from cast.wait_detection import (
    INCAPACITATING_STATES,
    build_forced_wait_plan,
    detect_wait_intent,
    is_incapacitated,
)


class TestDetectWaitIntentEnglish:
    """English wait keyword detection."""

    def test_slash_wait_command(self):
        assert detect_wait_intent("/wait") is True

    def test_plain_wait(self):
        assert detect_wait_intent("wait") is True

    def test_i_wait(self):
        assert detect_wait_intent("I wait") is True

    def test_do_nothing(self):
        assert detect_wait_intent("do nothing") is True

    def test_pass_turn(self):
        assert detect_wait_intent("pass") is True

    def test_skip_turn(self):
        assert detect_wait_intent("skip turn") is True

    def test_wait_with_target_not_detected(self):
        """'I wait for the merchant' is NOT a wait — it has a target."""
        assert detect_wait_intent("I wait for the merchant") is False

    def test_normal_action_not_detected(self):
        assert detect_wait_intent("I attack the guard") is False

    def test_explore_not_detected(self):
        assert detect_wait_intent("look around") is False

    def test_case_insensitive(self):
        assert detect_wait_intent("WAIT") is True
        assert detect_wait_intent("I WAIT") is True

    def test_do_nothing_variant(self):
        assert detect_wait_intent("I do nothing") is True

    def test_stand_still(self):
        assert detect_wait_intent("stand still") is True


class TestDetectWaitIntentRussian:
    """Russian wait keyword detection."""

    def test_zhdu(self):
        assert detect_wait_intent("жду", language="Russian") is True

    def test_pas(self):
        assert detect_wait_intent("пас", language="Russian") is True

    def test_nichego_ne_delayu(self):
        assert detect_wait_intent("ничего не делаю", language="Russian") is True

    def test_propuskayu_hod(self):
        assert detect_wait_intent("пропускаю ход", language="Russian") is True

    def test_normal_action_russian(self):
        assert detect_wait_intent("атакую стражника", language="Russian") is False


class TestIsIncapacitated:
    """Player state incapacitation check."""

    def test_healthy_not_incapacitated(self):
        assert is_incapacitated("healthy") is False

    def test_unconscious_is_incapacitated(self):
        assert is_incapacitated("unconscious") is True

    def test_stunned_is_incapacitated(self):
        assert is_incapacitated("stunned") is True

    def test_tied_up_is_incapacitated(self):
        assert is_incapacitated("tied up") is True

    def test_frightened_is_incapacitated(self):
        assert is_incapacitated("frightened") is True

    def test_frozen_is_incapacitated(self):
        assert is_incapacitated("frozen") is True

    def test_wounded_not_incapacitated(self):
        assert is_incapacitated("wounded") is False

    def test_case_insensitive(self):
        assert is_incapacitated("UNCONSCIOUS") is True
        assert is_incapacitated("Stunned") is True

    def test_incapacitating_states_is_frozenset(self):
        assert isinstance(INCAPACITATING_STATES, frozenset)


class TestBuildForcedWaitPlan:
    """Forced wait produces a valid routing plan."""

    def test_action_type_is_wait(self):
        plan = build_forced_wait_plan("unconscious")
        assert plan["action_type"] == "WAIT"

    def test_no_clarification_needed(self):
        plan = build_forced_wait_plan("stunned")
        assert plan["needs_clarification"] is False

    def test_empty_targets(self):
        plan = build_forced_wait_plan("tied up")
        assert plan["targets"] == []

    def test_not_aggressive(self):
        plan = build_forced_wait_plan("frightened")
        assert plan["is_aggressive"] is False

    def test_has_reason(self):
        plan = build_forced_wait_plan("unconscious")
        assert "unconscious" in plan.get("wait_reason", "")


class TestWaitInActionTypes:
    """WAIT is properly registered in the action system."""

    def test_wait_in_turn_counting_actions(self):
        from cast.constants import TURN_COUNTING_ACTIONS

        assert "WAIT" in TURN_COUNTING_ACTIONS

    def test_wait_has_time_cost(self):
        from timeline.time_costs import BASE_ACTION_COSTS

        assert "WAIT" in BASE_ACTION_COSTS
        assert BASE_ACTION_COSTS["WAIT"] > 0
