"""Unit tests for the deterministic scoring predicates baked into each scenario.

These tests exercise the pure predicate closures directly, feeding them
hand-crafted :class:`CapturedTurn` + :class:`GameState` snapshot fixtures.
No LLM calls are made — evidence-LLM elements live in their own
integration path covered by ``tests/benchmarks/test_scenarios.py``.
"""

from __future__ import annotations

import copy
from typing import Callable

import allure

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import DeterministicResult
from benchmarks.scenarios.autonomy_three_guards_tavern.elements import (
    ELEMENTS as AUTONOMY_ELEMENTS,
)
from benchmarks.scenarios.autonomy_three_guards_tavern.state import (
    build_state as build_autonomy_state,
)
from benchmarks.scenarios.memory_follow_up_marcus.elements import (
    ELEMENTS as MEMORY_ELEMENTS,
)
from benchmarks.scenarios.memory_follow_up_marcus.state import (
    build_state as build_memory_state,
)
from cast.schemas.turn_outputs import DialogueEntry, NPCTurnEntry, TurnOutputs
from models.game_state import GameState


def _predicate_for(elements: list, element_id: str) -> Callable:
    """Look up the deterministic check callable by element id."""
    for element in elements:
        if element.id == element_id:
            assert callable(element.check), "{0} is not a deterministic element".format(element_id)
            return element.check
    raise KeyError(element_id)


def _turn(index: int, player_action: str, outputs: TurnOutputs, narration: str = "") -> CapturedTurn:
    """Build a :class:`CapturedTurn` fixture — narration defaults to empty."""
    return CapturedTurn(
        index=index,
        player_action=player_action,
        narration=narration,
        turn_outputs=outputs,
        duration_ms=0,
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestMemoryScenarioPredicates:
    @allure.story("Memory scenario rubric")
    @allure.title("marcus_speaks_turn1 awards one point when Marcus appears in the turn's dialogue entries")
    def test_marcus_speaks_awards_point_when_marcus_replies(self):
        check = _predicate_for(MEMORY_ELEMENTS, "marcus_speaks_turn1")
        captured = [
            _turn(0, "greet", TurnOutputs()),
            _turn(
                1,
                "ask about loaf",
                TurnOutputs(dialogue=[DialogueEntry(npc_name="Marcus", response="Yes, yesterday...")]),
            ),
        ]

        result = check(captured, [])

        assert isinstance(result, DeterministicResult)
        assert result.awarded == 1
        assert "turn 1" in result.reason

    @allure.story("Memory scenario rubric")
    @allure.title("marcus_speaks_turn1 awards zero when no Marcus dialogue entry is present on that turn")
    def test_marcus_silent_awards_zero(self):
        check = _predicate_for(MEMORY_ELEMENTS, "marcus_speaks_turn1")
        captured = [
            _turn(0, "greet", TurnOutputs()),
            _turn(
                1,
                "ask about loaf",
                TurnOutputs(dialogue=[DialogueEntry(npc_name="Someone", response="Who?")]),
            ),
        ]

        result = check(captured, [])

        assert result.awarded == 0

    @allure.story("Memory scenario rubric")
    @allure.title("marcus_speaks_turn1 awards zero and records a clear reason when the scripted turn was not captured")
    def test_missing_turn_awards_zero(self):
        check = _predicate_for(MEMORY_ELEMENTS, "marcus_speaks_turn1")

        result = check([], [])

        assert result.awarded == 0
        assert "was not captured" in result.reason

    @allure.story("Memory scenario rubric")
    @allure.title("game_clock_advanced awards one point when the final snapshot's clock is ahead of the baseline")
    def test_game_clock_advanced_rewards_progress(self):
        check = _predicate_for(MEMORY_ELEMENTS, "game_clock_advanced")
        state = build_memory_state().game_state
        before = copy.deepcopy(state)
        after = copy.deepcopy(state)
        after.game_clock = before.game_clock + 0.25

        result = check([], [before, after])

        assert result.awarded == 1
        assert "advanced" in result.reason

    @allure.story("Memory scenario rubric")
    @allure.title("game_clock_advanced awards zero when the game clock did not move across the session")
    def test_game_clock_unchanged_awards_zero(self):
        check = _predicate_for(MEMORY_ELEMENTS, "game_clock_advanced")
        state = build_memory_state().game_state
        before = copy.deepcopy(state)
        after = copy.deepcopy(state)

        result = check([], [before, after])

        assert result.awarded == 0
        assert "did not advance" in result.reason

    @allure.story("Memory scenario rubric")
    @allure.title("marcus_history_grew awards full credit when at least three new entries appended to Marcus's log")
    def test_marcus_history_grew_full_credit(self):
        check = _predicate_for(MEMORY_ELEMENTS, "marcus_history_grew")
        before = build_memory_state().game_state
        after = copy.deepcopy(before)
        marcus_uuid = next(uuid for uuid, npc in after.npcs.items() if npc.name == "Marcus")
        after.npcs[marcus_uuid].conversation_history.extend(
            [
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
                {"role": "user", "content": "q2"},
            ],
        )

        result = check([], [before, after])

        assert result.awarded == 2
        assert "3" in result.reason

    @allure.story("Memory scenario rubric")
    @allure.title("marcus_history_grew awards partial credit when only one or two new entries were appended")
    def test_marcus_history_grew_partial_credit(self):
        check = _predicate_for(MEMORY_ELEMENTS, "marcus_history_grew")
        before = build_memory_state().game_state
        after = copy.deepcopy(before)
        marcus_uuid = next(uuid for uuid, npc in after.npcs.items() if npc.name == "Marcus")
        after.npcs[marcus_uuid].conversation_history.append({"role": "user", "content": "q"})

        result = check([], [before, after])

        assert result.awarded == 1

    @allure.story("Memory scenario rubric")
    @allure.title("marcus_history_grew awards zero when Marcus's conversation history did not grow")
    def test_marcus_history_unchanged(self):
        check = _predicate_for(MEMORY_ELEMENTS, "marcus_history_grew")
        before = build_memory_state().game_state
        after = copy.deepcopy(before)

        result = check([], [before, after])

        assert result.awarded == 0

    @allure.story("Memory scenario rubric")
    @allure.title("marcus_history_grew reports zero when Marcus is absent from the snapshot NPC map")
    def test_marcus_missing_from_state(self):
        check = _predicate_for(MEMORY_ELEMENTS, "marcus_history_grew")
        before = build_memory_state().game_state
        after = copy.deepcopy(before)
        before.npcs.clear()
        after.npcs.clear()

        result = check([], [before, after])

        assert result.awarded == 0
        assert "not registered" in result.reason


def _autonomy_state() -> GameState:
    """Fresh autonomy :class:`GameState` scoped per test to avoid aliasing."""
    return build_autonomy_state().game_state


def _punch_turn(npc_entries: list[NPCTurnEntry], dialogue: list[DialogueEntry] | None = None) -> CapturedTurn:
    """Build the punch-turn fixture (turn index 1 in this scenario)."""
    outputs = TurnOutputs(npc_turns=npc_entries, dialogue=dialogue or [])
    return _turn(1, "punch Aulus", outputs)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestAutonomyScenarioPredicates:
    @allure.story("Autonomy scenario rubric")
    @allure.title("bystanders_not_idle awards full credit when both Bassus and Cato produce non-IDLE npc_turns")
    def test_both_bystanders_act(self):
        check = _predicate_for(AUTONOMY_ELEMENTS, "bystanders_not_idle")
        punch = _punch_turn(
            [
                NPCTurnEntry(npc_name="Bassus", action="draws sword", action_type="COMBAT"),
                NPCTurnEntry(npc_name="Cato", action="lunges to restrain", action_type="RESTRAIN"),
            ],
        )

        result = check([_turn(0, "look", TurnOutputs()), punch], [])

        assert result.awarded == 3

    @allure.story("Autonomy scenario rubric")
    @allure.title("bystanders_not_idle awards partial credit when only one bystander reacts non-idly")
    def test_one_bystander_acts(self):
        check = _predicate_for(AUTONOMY_ELEMENTS, "bystanders_not_idle")
        punch = _punch_turn(
            [
                NPCTurnEntry(npc_name="Bassus", action="draws sword", action_type="COMBAT"),
                NPCTurnEntry(npc_name="Cato", action="watches", action_type="IDLE"),
            ],
        )

        result = check([_turn(0, "look", TurnOutputs()), punch], [])

        assert result.awarded == 2
        assert "Bassus" in result.reason

    @allure.story("Autonomy scenario rubric")
    @allure.title("bystanders_not_idle awards zero when neither bystander produces a non-IDLE action")
    def test_no_bystander_acts(self):
        check = _predicate_for(AUTONOMY_ELEMENTS, "bystanders_not_idle")
        punch = _punch_turn(
            [
                NPCTurnEntry(npc_name="Bassus", action="stays still", action_type="IDLE"),
                NPCTurnEntry(npc_name="Cato", action="watches", action_type="IDLE"),
            ],
        )

        result = check([_turn(0, "look", TurnOutputs()), punch], [])

        assert result.awarded == 0

    @allure.story("Autonomy scenario rubric")
    @allure.title("aulus_contest_roll awards two points when Aulus's dialogue entry carries a contest_roll string")
    def test_aulus_contest_roll_present(self):
        check = _predicate_for(AUTONOMY_ELEMENTS, "aulus_contest_roll")
        punch = _punch_turn(
            [],
            dialogue=[
                DialogueEntry(
                    npc_name="Aulus",
                    response="You dare?!",
                    contest_roll="player 14 vs aulus 9 — HIT",
                ),
            ],
        )

        result = check([_turn(0, "look", TurnOutputs()), punch], [])

        assert result.awarded == 2
        assert result.evidence_quote is not None
        assert "HIT" in result.evidence_quote

    @allure.story("Autonomy scenario rubric")
    @allure.title("aulus_contest_roll awards zero when Aulus's dialogue entry has no contest_roll attached")
    def test_aulus_contest_roll_absent(self):
        check = _predicate_for(AUTONOMY_ELEMENTS, "aulus_contest_roll")
        punch = _punch_turn(
            [],
            dialogue=[DialogueEntry(npc_name="Aulus", response="You dare?!", contest_roll=None)],
        )

        result = check([_turn(0, "look", TurnOutputs()), punch], [])

        assert result.awarded == 0

    @allure.story("Autonomy scenario rubric")
    @allure.title("bystander_moods_shifted awards one point per bystander whose mood changed from the baseline")
    def test_both_moods_shift(self):
        check = _predicate_for(AUTONOMY_ELEMENTS, "bystander_moods_shifted")
        before = _autonomy_state()
        after = copy.deepcopy(before)
        for npc in after.npcs.values():
            if npc.name in {"Bassus", "Cato"}:
                npc.current_mood = "hostile"

        result = check([_turn(0, "look", TurnOutputs()), _punch_turn([])], [before, before, after])

        assert result.awarded == 2

    @allure.story("Autonomy scenario rubric")
    @allure.title("bystander_moods_shifted awards one point when only one bystander's mood changed")
    def test_one_mood_shifts(self):
        check = _predicate_for(AUTONOMY_ELEMENTS, "bystander_moods_shifted")
        before = _autonomy_state()
        after = copy.deepcopy(before)
        for npc in after.npcs.values():
            if npc.name == "Bassus":
                npc.current_mood = "angry"

        result = check([_turn(0, "look", TurnOutputs()), _punch_turn([])], [before, before, after])

        assert result.awarded == 1
        assert "Bassus" in result.reason

    @allure.story("Autonomy scenario rubric")
    @allure.title("bystander_moods_shifted awards zero when both bystanders' moods stayed at the baseline value")
    def test_no_mood_shift(self):
        check = _predicate_for(AUTONOMY_ELEMENTS, "bystander_moods_shifted")
        before = _autonomy_state()
        after = copy.deepcopy(before)

        result = check([_turn(0, "look", TurnOutputs()), _punch_turn([])], [before, before, after])

        assert result.awarded == 0

    @allure.story("Autonomy scenario rubric")
    @allure.title("bystander_moods_shifted awards zero when the expected post-punch snapshot is missing from the list")
    def test_missing_post_punch_snapshot(self):
        check = _predicate_for(AUTONOMY_ELEMENTS, "bystander_moods_shifted")
        before = _autonomy_state()

        result = check([_turn(0, "look", TurnOutputs()), _punch_turn([])], [before])

        assert result.awarded == 0
        assert "post-punch snapshot missing" in result.reason
