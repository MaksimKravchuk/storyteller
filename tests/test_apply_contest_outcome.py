"""Unit tests for the contest-outcome predict/commit split."""

from __future__ import annotations

import allure

from cast._npc_outcome import OutcomeKind, commit_outcome, predict_contest_outcome
from cast.dice import ContestOutcome, ContestRoll, ContestType
from models.goal import GoalKind
from models.npc_card import NPCCard
from models.relationship import RelationshipKind


_ATTACKER = NPCCard(name="Brutus", occupation="legionary")


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
        commit_outcome(_ATTACKER, target, predicted)
        assert target.physical_status == "dead"

    @allure.story("Mood commit")
    @allure.title("commit_outcome with MOOD kind writes current_mood")
    def test_mood_commit_writes_current_mood(self) -> None:
        target = NPCCard(name="Marcus", occupation="merchant", current_mood="neutral")
        predicted = predict_contest_outcome(_intimidation_roll(ContestOutcome.ACTOR_DOMINATES))
        assert predicted is not None
        commit_outcome(_ATTACKER, target, predicted)
        assert target.current_mood == "frightened"


def _commit_against_fresh_target(roll: ContestRoll) -> NPCCard:
    target = NPCCard(name="Marcus", occupation="merchant", current_mood="neutral")
    predicted = predict_contest_outcome(roll)
    assert predicted is not None
    commit_outcome(_ATTACKER, target, predicted, turn=4)
    return target


@allure.epic("Combat & Action Resolution")
@allure.feature("NPC autonomous contest outcomes")
class TestCommitOutcomeGrudge:
    """A surviving victim of an autonomous contest holds a grudge against the attacker."""

    @allure.story("Grudge")
    @allure.title("A wounded victim turns ENEMY toward the attacker and gains a KILL goal")
    def test_wounded_victim_forms_grudge(self) -> None:
        target = _commit_against_fresh_target(_combat_roll(ContestOutcome.ACTOR_SUCCEEDS))
        rel = next(r for r in target.relationships if r.target_uuid == str(_ATTACKER.uuid))
        assert rel.kind is RelationshipKind.ENEMY
        assert rel.intensity == -2
        assert rel.established_turn == 4
        assert target.life_goal is not None
        assert target.life_goal.kind is GoalKind.KILL
        assert target.life_goal.target_uuid == _ATTACKER.uuid

    @allure.story("Grudge")
    @allure.title("An intimidated victim also forms a grudge")
    def test_intimidated_victim_forms_grudge(self) -> None:
        target = _commit_against_fresh_target(_intimidation_roll(ContestOutcome.ACTOR_DOMINATES))
        assert target.relationships[0].kind is RelationshipKind.ENEMY
        assert target.life_goal is not None

    @allure.story("Grudge")
    @allure.title("A killed victim forms no grudge")
    def test_dead_victim_forms_no_grudge(self) -> None:
        target = _commit_against_fresh_target(_combat_roll(ContestOutcome.ACTOR_DOMINATES))
        assert target.relationships == []
        assert target.life_goal is None
