"""Deterministic-element tests for the escalation benchmark scenario."""

from __future__ import annotations

from typing import Callable

import allure

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.scenarios.escalation_guard_assault.elements import ELEMENTS
from benchmarks.scenarios.escalation_guard_assault.state import (
    SENTRY_CHALLENGE_FORMULA,
    SENTRY_UUID,
    build_state,
)
from cast.schemas.turn_outputs import DialogueEntry, TurnOutputs
from models.game_state import GameState


def _predicate_for(element_id: str) -> Callable:
    """Look up the deterministic check callable by element id."""
    for element in ELEMENTS:
        if element.id == element_id:
            assert callable(element.check), "{0} is not a deterministic element".format(element_id)
            return element.check
    raise KeyError(element_id)


def _turn(index: int, player_action: str, outputs: TurnOutputs) -> CapturedTurn:
    return CapturedTurn(
        index=index,
        player_action=player_action,
        narration="",
        turn_outputs=outputs,
        duration_ms=0,
    )


def _escalation_snapshots(levels: list[int], final_mood: str = "threatened") -> list[GameState]:
    """Build a list of escalation snapshots with the given sentry hostility_level per turn."""
    snapshots: list[GameState] = []
    final_index = len(levels) - 1
    for index, level in enumerate(levels):
        snap = build_state().game_state
        snap.npcs[SENTRY_UUID].hostility_level = level
        if index == final_index:
            snap.npcs[SENTRY_UUID].current_mood = final_mood
        snapshots.append(snap)
    return snapshots


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestEscalationScenarioPredicates:
    @allure.story("Escalation scenario rubric")
    @allure.title("hostility_monotonic awards full credit when hostility_level strictly increases every assault turn")
    def test_hostility_increases_across_turns(self):
        check = _predicate_for("hostility_monotonic")
        snapshots = _escalation_snapshots([0, 2, 4, 6])

        result = check([], snapshots)

        assert result.awarded == 3
        assert "increased each turn" in result.reason

    @allure.story("Escalation scenario rubric")
    @allure.title("hostility_monotonic awards zero when the sentry's hostility stays flat across turns")
    def test_hostility_flat_awards_zero(self):
        check = _predicate_for("hostility_monotonic")
        snapshots = _escalation_snapshots([0, 0, 0, 0])

        result = check([], snapshots)

        assert result.awarded == 0
        assert "did not strictly increase" in result.reason

    @allure.story("Escalation scenario rubric")
    @allure.title("final_mood_retaliating awards credit when the final mood has an aggression threshold")
    def test_final_mood_in_aggression_set(self):
        check = _predicate_for("final_mood_retaliating")
        snapshots = _escalation_snapshots([0, 2, 4, 6], final_mood="hostile")

        result = check([], snapshots)

        assert result.awarded == 2

    @allure.story("Escalation scenario rubric")
    @allure.title("final_mood_retaliating awards zero when the final mood is a peaceful one like neutral")
    def test_final_mood_neutral_awards_zero(self):
        check = _predicate_for("final_mood_retaliating")
        snapshots = _escalation_snapshots([0, 2, 4, 6], final_mood="neutral")

        result = check([], snapshots)

        assert result.awarded == 0

    @allure.story("Escalation scenario rubric")
    @allure.title("formula_not_repeated awards zero when the sentry still recites the exact challenge formula on T3")
    def test_formula_repeated_on_t3_awards_zero(self):
        check = _predicate_for("formula_not_repeated")
        captured = [
            _turn(0, "punch", TurnOutputs()),
            _turn(1, "stomp", TurnOutputs()),
            _turn(
                2,
                "knee",
                TurnOutputs(dialogue=[DialogueEntry(npc_name="Quintus", response=SENTRY_CHALLENGE_FORMULA)]),
            ),
        ]

        result = check(captured, [])

        assert result.awarded == 0
        assert result.evidence_quote == SENTRY_CHALLENGE_FORMULA

    @allure.story("Escalation scenario rubric")
    @allure.title("formula_not_repeated awards full credit when the sentry has broken out of the standing-orders loop")
    def test_formula_absent_on_t3_awards_credit(self):
        check = _predicate_for("formula_not_repeated")
        captured = [
            _turn(0, "punch", TurnOutputs()),
            _turn(1, "stomp", TurnOutputs()),
            _turn(
                2,
                "knee",
                TurnOutputs(dialogue=[DialogueEntry(npc_name="Quintus", response="*draws his gladius and lunges*")]),
            ),
        ]

        result = check(captured, [])

        assert result.awarded == 3
