"""Regression tests for the deterministic scene-builder re-entry predicate.

``prose_consistent_on_return`` was converted from an evidence-LLM element to a
deterministic closed-set landmark membership test (ADR-0013). These tests pin
the predicate directly against hand-crafted captured turns.
"""

from __future__ import annotations

import allure

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import DeterministicResult
from benchmarks.scenarios.scene_builder_re_entry_consistency.elements import ELEMENTS
from benchmarks.scenarios.scene_builder_re_entry_consistency.state import FORUM_POIS
from cast.schemas.turn_outputs import TurnOutputs


def _check():
    for element in ELEMENTS:
        if element.id == "prose_consistent_on_return":
            assert callable(element.check), "prose_consistent_on_return is not deterministic"
            return element.check
    raise KeyError("prose_consistent_on_return")


def _turn(index: int, narration: str = "") -> CapturedTurn:
    return CapturedTurn(
        index=index,
        player_action="move",
        narration=narration,
        turn_outputs=TurnOutputs(),
        duration_ms=0,
    )


def _four_turns(re_entry_narration: str) -> list[CapturedTurn]:
    """Forum → south → south → re-entry; only the re-entry narration matters here."""
    return [
        _turn(0, "The Forum opens before you."),
        _turn(1),
        _turn(2),
        _turn(3, re_entry_narration),
    ]


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestSceneBuilderReEntryPredicate:
    @allure.story("Scene-builder re-entry rubric")
    @allure.title("prose_consistent_on_return awards full credit when re-entry narration names a seeded landmark")
    def test_awards_when_landmark_named(self):
        landmark = FORUM_POIS[1]  # "Temple of Saturn"
        captured = _four_turns("Back in the Forum, the {0} rises ahead of you.".format(landmark))

        result = _check()(captured, [])

        assert isinstance(result, DeterministicResult)
        assert result.awarded == 2
        assert landmark in result.reason

    @allure.story("Scene-builder re-entry rubric")
    @allure.title("prose_consistent_on_return matches landmark names case-insensitively")
    def test_matches_case_insensitively(self):
        captured = _four_turns("You climb back toward the ROSTRA and the bustle of the square.")

        result = _check()(captured, [])

        assert result.awarded == 2

    @allure.story("Scene-builder re-entry rubric")
    @allure.title("prose_consistent_on_return awards credit for a paraphrased landmark alias")
    def test_matches_landmark_alias(self):
        # "Saturn's temple" is a valid paraphrase of the seeded "Temple of Saturn"
        # — the old judge prompt accepted these, so the deterministic check must too.
        captured = _four_turns("You re-enter the Forum; Saturn's temple looms over the square.")

        result = _check()(captured, [])

        assert result.awarded == 2
        assert "Temple of Saturn" in result.reason

    @allure.story("Scene-builder re-entry rubric")
    @allure.title("prose_consistent_on_return awards zero when the re-entry narration names no seeded landmark")
    def test_awards_zero_without_landmark(self):
        captured = _four_turns("You return to a busy junction of awnings, stalls, and drainage channels.")

        result = _check()(captured, [])

        assert result.awarded == 0
        assert "none of the seeded" in result.reason

    @allure.story("Scene-builder re-entry rubric")
    @allure.title("prose_consistent_on_return awards zero when the re-entry turn was not captured")
    def test_awards_zero_when_turn_missing(self):
        result = _check()([_turn(0)], [])

        assert result.awarded == 0
        assert "was not captured" in result.reason
