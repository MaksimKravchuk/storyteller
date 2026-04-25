"""Unit tests for the contest-outcome predict/commit split."""

from __future__ import annotations

import allure

from cast._npc_outcome import OutcomeKind, commit_outcome, predict_contest_outcome
from cast.dice import ContestOutcome, ContestRoll, ContestType
from models.npc_card import NPCCard


def _combat_roll(outcome: ContestOutcome) -> ContestRoll:
    return ContestRoll(
        contest_type=ContestType.COMBAT,
        outcome=outcome,
        actor_roll=10,
        target_roll=5,
        actor_bonus=0,
        target_bonus=0,
    )


def _intimidation_roll(outcome: ContestOutcome) -> ContestRoll:
    return ContestRoll(
        contest_type=ContestType.INTIMIDATION,
        outcome=outcome,
        actor_roll=10,
        target_roll=5,
        actor_bonus=0,
        target_bonus=0,
    )


@allure.epic("Combat & Action Resolution")
@allure.feature("NPC autonomous contest outcomes")
class TestPredictContestOutcome:
    """``predict_contest_outcome`` is pure: it reads dice without mutating."""

    @allure.story("Combat lethality")
    @allure.title("ATTACK with ACTOR_DOMINATES predicts a lethal physical outcome")
    def test_attack_dominates_predicts_dead(self) -> None:
        predicted = predict_contest_outcome(_combat_roll(ContestOutcome.ACTOR_DOMINATES))
        assert predicted is not None
        assert predicted.new_value == "dead"
        assert predicted.kind is OutcomeKind.PHYSICAL

    @allure.story("Combat wounds")
    @allure.title("ATTACK with ACTOR_SUCCEEDS predicts a wounding physical outcome")
    def test_attack_succeeds_predicts_wounded(self) -> None:
        predicted = predict_contest_outcome(_combat_roll(ContestOutcome.ACTOR_SUCCEEDS))
        assert predicted is not None
        assert predicted.new_value == "wounded"
        assert predicted.kind is OutcomeKind.PHYSICAL

    @allure.story("Combat resistance")
    @allure.title("Target-favoring outcomes return None (no state change)")
    def test_target_resists_no_change(self) -> None:
        for outcome in (ContestOutcome.TARGET_RESISTS, ContestOutcome.TARGET_DOMINATES):
            assert predict_contest_outcome(_combat_roll(outcome)) is None

    @allure.story("Intimidation")
    @allure.title("INTIMIDATION with ACTOR_DOMINATES predicts a mood change")
    def test_intimidation_dominates_predicts_frightened(self) -> None:
        predicted = predict_contest_outcome(_intimidation_roll(ContestOutcome.ACTOR_DOMINATES))
        assert predicted is not None
        assert predicted.new_value == "frightened"
        assert predicted.kind is OutcomeKind.MOOD

    @allure.story("No-op cases")
    @allure.title("None roll returns None and predicts nothing")
    def test_none_roll_returns_none(self) -> None:
        assert predict_contest_outcome(None) is None


@allure.epic("Combat & Action Resolution")
@allure.feature("NPC autonomous contest outcomes")
class TestCommitOutcome:
    """``commit_outcome`` writes the predicted value to the right target field."""

    @allure.story("Physical commit")
    @allure.title("commit_outcome with PHYSICAL kind writes physical_status")
    def test_physical_commit_writes_physical_status(self) -> None:
        target = NPCCard(name="Marcus", occupation="merchant")
        predicted = predict_contest_outcome(_combat_roll(ContestOutcome.ACTOR_DOMINATES))
        assert predicted is not None
        commit_outcome(target, predicted)
        assert target.physical_status == "dead"

    @allure.story("Mood commit")
    @allure.title("commit_outcome with MOOD kind writes current_mood")
    def test_mood_commit_writes_current_mood(self) -> None:
        target = NPCCard(name="Marcus", occupation="merchant", current_mood="neutral")
        predicted = predict_contest_outcome(_intimidation_roll(ContestOutcome.ACTOR_DOMINATES))
        assert predicted is not None
        commit_outcome(target, predicted)
        assert target.current_mood == "frightened"
