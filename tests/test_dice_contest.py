"""Tests for the generic contest dice system that replaces combat-only dice."""

from __future__ import annotations

import random
from collections.abc import Iterator

import allure

from cast.dice import (
    CONTEST_SKILL_MAP,
    ContestOutcome,
    ContestRoll,
    ContestType,
    contest_roll_to_dict,
    roll_contest,
)

_D20 = 20

_SKILL_HIGH = 10
_SKILL_MID = 5
_SKILL_LOW = 2
_SKILL_ZERO = 0
_SKILL_SEVEN = 7

_ROLL_THREE = 3
_ROLL_FIVE = 5
_ROLL_SEVEN = 7
_ROLL_EIGHT = 8
_ROLL_TEN = 10
_ROLL_TWELVE = 12
_ROLL_THIRTEEN = 13
_ROLL_FOURTEEN = 14
_ROLL_FIFTEEN = 15
_ROLL_SIXTEEN = 16
_ROLL_EIGHTEEN = 18

_FUZZ_SEED = 12345
_FUZZ_ITERATIONS = 200

# random.Random(31)'s first randint(1, 20) is 1 → actor_roll == 1.
_SEED_ACTOR_ONE = 31
# random.Random(15)'s second randint(1, 20) is 1 → target_roll == 1.
_SEED_TARGET_ONE = 15


class _FakeRng:
    """Fake RNG for deterministic dice tests.

    Yields actor roll first, then target roll.
    When given *fixed*, always returns that value.
    """

    def __init__(
        self,
        *,
        actor: int | None = None,
        target: int | None = None,
        fixed: int | None = None,
    ) -> None:
        if fixed is None:
            rolls: list[int] = [actor or 0, target or 0]
        else:
            rolls = [fixed, fixed]
        self._calls: Iterator[int] = iter(rolls)

    def randint(self, low: int, high: int) -> int:  # noqa: WPS110
        return next(self._calls)


def _rng(
    *,
    actor: int | None = None,
    target: int | None = None,
    fixed: int | None = None,
) -> random.Random:
    """Build a _FakeRng cast to random.Random."""
    return _FakeRng(actor=actor, target=target, fixed=fixed)  # type: ignore[return-value]


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestContestTypeEnum:
    """All expected contest types exist."""

    @allure.story("Contest type catalogue")
    @allure.title("Combat is one of the supported contest types")
    def test_combat_type(self):
        assert ContestType.COMBAT.value == "combat"

    @allure.story("Contest type catalogue")
    @allure.title("Persuasion is one of the supported contest types")
    def test_persuasion_type(self):
        assert ContestType.PERSUASION.value == "persuasion"

    @allure.story("Contest type catalogue")
    @allure.title("Deception is one of the supported contest types")
    def test_deception_type(self):
        assert ContestType.DECEPTION.value == "deception"

    @allure.story("Contest type catalogue")
    @allure.title("Intimidation is one of the supported contest types")
    def test_intimidation_type(self):
        assert ContestType.INTIMIDATION.value == "intimidation"

    @allure.story("Contest type catalogue")
    @allure.title("Stealth is one of the supported contest types")
    def test_stealth_type(self):
        assert ContestType.STEALTH.value == "stealth"

    @allure.story("Contest type catalogue")
    @allure.title("Exactly five contest types are supported (combat, persuasion, deception, intimidation, stealth)")
    def test_five_types_total(self):
        assert len(ContestType) == 5


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestContestOutcomeEnum:
    """All expected contest outcomes exist."""

    @allure.story("Outcome catalogue")
    @allure.title("ACTOR_DOMINATES is a recognized contest outcome")
    def test_actor_dominates(self):
        assert ContestOutcome.ACTOR_DOMINATES.value == "actor_dominates"

    @allure.story("Outcome catalogue")
    @allure.title("ACTOR_SUCCEEDS is a recognized contest outcome")
    def test_actor_succeeds(self):
        assert ContestOutcome.ACTOR_SUCCEEDS.value == "actor_succeeds"

    @allure.story("Outcome catalogue")
    @allure.title("TARGET_RESISTS is a recognized contest outcome")
    def test_target_resists(self):
        assert ContestOutcome.TARGET_RESISTS.value == "target_resists"

    @allure.story("Outcome catalogue")
    @allure.title("TARGET_DOMINATES is a recognized contest outcome")
    def test_target_dominates(self):
        assert ContestOutcome.TARGET_DOMINATES.value == "target_dominates"

    @allure.story("Outcome catalogue")
    @allure.title("Exactly four contest outcome categories are defined")
    def test_four_outcomes_total(self):
        assert len(ContestOutcome) == 4


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestContestSkillMap:
    """CONTEST_SKILL_MAP maps every ContestType to (actor_attr, target_attr)."""

    @allure.story("Skill routing")
    @allure.title("Every contest type has an entry in the CONTEST_SKILL_MAP")
    def test_has_all_types(self):
        for ct in ContestType:
            assert ct in CONTEST_SKILL_MAP, f"Missing map entry for {ct}"

    @allure.story("Skill routing")
    @allure.title("Combat contests use the combat_skill attribute for both actor and target")
    def test_combat_maps_to_combat_skill(self):
        assert CONTEST_SKILL_MAP[ContestType.COMBAT] == ("combat_skill", "combat_skill")

    @allure.story("Skill routing")
    @allure.title("Persuasion contests use the persuasion_skill attribute on both sides")
    def test_persuasion_maps_to_persuasion_skill(self):
        assert CONTEST_SKILL_MAP[ContestType.PERSUASION] == ("persuasion_skill", "persuasion_skill")

    @allure.story("Skill routing")
    @allure.title("Deception contests use the deception_skill attribute on both sides")
    def test_deception_maps_to_deception_skill(self):
        assert CONTEST_SKILL_MAP[ContestType.DECEPTION] == ("deception_skill", "deception_skill")

    @allure.story("Skill routing")
    @allure.title("Intimidation contests use the intimidation_skill attribute on both sides")
    def test_intimidation_maps_to_intimidation_skill(self):
        assert CONTEST_SKILL_MAP[ContestType.INTIMIDATION] == ("intimidation_skill", "intimidation_skill")

    @allure.story("Skill routing")
    @allure.title("Stealth contests pit the actor's stealth_skill against the target's perception_skill")
    def test_stealth_actor_uses_stealth_target_uses_perception(self):
        assert CONTEST_SKILL_MAP[ContestType.STEALTH] == ("stealth_skill", "perception_skill")


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestRollContestOutcomes:
    """Outcome classification based on diff = target_total - actor_total."""

    @allure.story("Outcome classification")
    @allure.title("A large target advantage classifies the contest as TARGET_DOMINATES")
    def test_target_dominates_high_diff(self):
        # target total = 18 + 10 = 28, actor total = 5 + 0 = 5, diff = 23
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_HIGH, _rng=_rng(actor=_ROLL_FIVE, target=_ROLL_EIGHTEEN))
        assert result.outcome == ContestOutcome.TARGET_DOMINATES

    @allure.story("Outcome classification")
    @allure.title("A slim target edge classifies the contest as TARGET_RESISTS")
    def test_target_resists(self):
        # target total = 10 + 5 = 15, actor total = 14 + 0 = 14, diff = 1
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_MID, _rng=_rng(actor=_ROLL_FOURTEEN, target=_ROLL_TEN))
        assert result.outcome == ContestOutcome.TARGET_RESISTS

    @allure.story("Outcome classification")
    @allure.title("A moderate actor advantage classifies the contest as ACTOR_SUCCEEDS")
    def test_actor_succeeds(self):
        # target total = 8 + 2 = 10, actor total = 13 + 0 = 13, diff = -3
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_LOW, _rng=_rng(actor=_ROLL_THIRTEEN, target=_ROLL_EIGHT))
        assert result.outcome == ContestOutcome.ACTOR_SUCCEEDS

    @allure.story("Outcome classification")
    @allure.title("A large actor advantage over an unskilled target classifies as ACTOR_DOMINATES")
    def test_actor_dominates(self):
        # target total = 3 + 0 = 3, actor total = 15 + 0 = 15, diff = -12
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_ZERO, _rng=_rng(actor=_ROLL_FIFTEEN, target=_ROLL_THREE))
        assert result.outcome == ContestOutcome.ACTOR_DOMINATES

    @allure.story("Outcome classification")
    @allure.title("With zero skill on both sides a tied roll defaults to TARGET_RESISTS")
    def test_zero_skill_no_bonus(self):
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_ZERO, _rng=_rng(actor=_ROLL_TEN, target=_ROLL_TEN))
        assert result.actor_bonus == 0
        assert result.target_bonus == 0
        assert result.outcome == ContestOutcome.TARGET_RESISTS


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestRollContestBoundaries:
    """Exact boundary conditions for outcome thresholds."""

    @allure.story("Boundary conditions")
    @allure.title("A contest with margin of exactly 0 (target wins ties) resolves to TARGET_RESISTS")
    def test_boundary_target_resists_at_zero(self):
        # target total = 10 + 5 = 15, actor total = 15 + 0 = 15, diff = 0
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_MID, _rng=_rng(actor=_ROLL_FIFTEEN, target=_ROLL_TEN))
        assert result.outcome == ContestOutcome.TARGET_RESISTS

    @allure.story("Boundary conditions")
    @allure.title("A contest with margin -1 (one point in the actor's favor) flips to ACTOR_SUCCEEDS")
    def test_boundary_actor_succeeds_at_minus_one(self):
        # target total = 10 + 5 = 15, actor total = 16 + 0 = 16, diff = -1
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_MID, _rng=_rng(actor=_ROLL_SIXTEEN, target=_ROLL_TEN))
        assert result.outcome == ContestOutcome.ACTOR_SUCCEEDS

    @allure.story("Boundary conditions")
    @allure.title("A margin of +5 in the target's favor promotes the outcome to TARGET_DOMINATES")
    def test_boundary_target_dominates_at_five(self):
        # target total = 10 + 5 = 15, actor total = 10 + 0 = 10, diff = 5
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_MID, _rng=_rng(actor=_ROLL_TEN, target=_ROLL_TEN))
        assert result.outcome == ContestOutcome.TARGET_DOMINATES

    @allure.story("Boundary conditions")
    @allure.title("A margin of exactly -5 in the actor's favor stays ACTOR_SUCCEEDS (not yet dominating)")
    def test_boundary_actor_succeeds_at_minus_five(self):
        # target total = 10 + 0 = 10, actor total = 15 + 0 = 15, diff = -5
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_ZERO, _rng=_rng(actor=_ROLL_FIFTEEN, target=_ROLL_TEN))
        assert result.outcome == ContestOutcome.ACTOR_SUCCEEDS

    @allure.story("Boundary conditions")
    @allure.title("A margin of -6 in the actor's favor promotes the outcome to ACTOR_DOMINATES")
    def test_boundary_actor_dominates_at_minus_six(self):
        # target total = 7 + 0 = 7, actor total = 13 + 0 = 13, diff = -6
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_ZERO, _rng=_rng(actor=_ROLL_THIRTEEN, target=_ROLL_SEVEN))
        assert result.outcome == ContestOutcome.ACTOR_DOMINATES

    @allure.story("Boundary conditions")
    @allure.title("The actor's skill bonus is added to (not subtracted from) the actor total")
    def test_actor_skill_added_to_actor_total(self):
        # actor total = 10 + 5 = 15, target total = 10 + 0 = 10, diff = -5 → ACTOR_SUCCEEDS.
        # If the skill were subtracted, actor total = 5, diff = +5 → TARGET_DOMINATES.
        result = roll_contest(ContestType.COMBAT, _SKILL_MID, _SKILL_ZERO, _rng=_rng(actor=_ROLL_TEN, target=_ROLL_TEN))
        assert result.outcome == ContestOutcome.ACTOR_SUCCEEDS


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestRollContestFields:
    """Roll values are correctly recorded."""

    @allure.story("Recorded values")
    @allure.title("ContestRoll records actor roll, target roll, and both skill bonuses on the result")
    def test_roll_values_recorded(self):
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_SEVEN, _rng=_rng(actor=_ROLL_EIGHT, target=_ROLL_TWELVE))
        assert result.actor_roll == _ROLL_EIGHT
        assert result.target_roll == _ROLL_TWELVE
        assert result.actor_bonus == 0
        assert result.target_bonus == _SKILL_SEVEN

    @allure.story("Recorded values")
    @allure.title("ContestRoll carries its originating contest type on the result object")
    def test_contest_type_recorded(self):
        result = roll_contest(ContestType.PERSUASION, 0, _SKILL_MID, _rng=_rng(fixed=_ROLL_TEN))
        assert result.contest_type == ContestType.PERSUASION

    @allure.story("Recorded values")
    @allure.title("Both actor and target skill bonuses are captured on the ContestRoll result")
    def test_both_bonuses_recorded(self):
        result = roll_contest(ContestType.DECEPTION, 3, _SKILL_MID, _rng=_rng(fixed=_ROLL_TEN))
        assert result.actor_bonus == 3
        assert result.target_bonus == _SKILL_MID


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestContestRollDescription:
    """Each outcome has a non-empty description."""

    @allure.story("Narrative descriptions")
    @allure.title("Every combination of contest type and outcome has a non-empty narrative description")
    def test_all_outcomes_have_descriptions(self):
        for outcome in ContestOutcome:
            for ct in ContestType:
                roll = ContestRoll(
                    contest_type=ct,
                    outcome=outcome,
                    actor_roll=_ROLL_TEN,
                    target_roll=_ROLL_TEN,
                    actor_bonus=0,
                    target_bonus=0,
                )
                assert len(roll.description) > 0

    @allure.story("Narrative descriptions")
    @allure.title("Combat contest descriptions mention physical action words like blow, hit, or strike")
    def test_combat_descriptions_mention_physical(self):
        roll = ContestRoll(
            contest_type=ContestType.COMBAT,
            outcome=ContestOutcome.ACTOR_DOMINATES,
            actor_roll=_ROLL_TEN,
            target_roll=_ROLL_TEN,
            actor_bonus=0,
            target_bonus=0,
        )
        desc = roll.description.lower()
        assert any(word in desc for word in ("blow", "hit", "attack", "overwhelm", "strike", "devastat"))

    @allure.story("Narrative descriptions")
    @allure.title("Social contest types use the social description text, distinct from the stealth text")
    def test_social_type_uses_social_not_stealth_descriptions(self):
        persuasion_desc = ContestRoll(
            contest_type=ContestType.PERSUASION,
            outcome=ContestOutcome.ACTOR_DOMINATES,
            actor_roll=_ROLL_TEN,
            target_roll=_ROLL_TEN,
            actor_bonus=0,
            target_bonus=0,
        ).description
        stealth_desc = ContestRoll(
            contest_type=ContestType.STEALTH,
            outcome=ContestOutcome.ACTOR_DOMINATES,
            actor_roll=_ROLL_TEN,
            target_roll=_ROLL_TEN,
            actor_bonus=0,
            target_bonus=0,
        ).description
        # The social branch must NOT collapse into the stealth branch.
        assert persuasion_desc != stealth_desc
        assert "convinced" in persuasion_desc
        assert "invisible" in stealth_desc


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestRollContestSocialTypes:
    """Non-combat contest types work correctly."""

    @allure.story("Social contest types")
    @allure.title("Persuasion contests resolve using the generic contest machinery")
    def test_persuasion_contest(self):
        result = roll_contest(ContestType.PERSUASION, 0, _SKILL_MID, _rng=_rng(actor=_ROLL_FIFTEEN, target=_ROLL_TEN))
        assert result.contest_type == ContestType.PERSUASION
        assert result.outcome == ContestOutcome.TARGET_RESISTS

    @allure.story("Social contest types")
    @allure.title("Deception contests resolve using the generic contest machinery")
    def test_deception_contest(self):
        result = roll_contest(ContestType.DECEPTION, 0, _SKILL_ZERO, _rng=_rng(actor=_ROLL_FIFTEEN, target=_ROLL_THREE))
        assert result.contest_type == ContestType.DECEPTION
        assert result.outcome == ContestOutcome.ACTOR_DOMINATES

    @allure.story("Social contest types")
    @allure.title("Intimidation contests resolve using the generic contest machinery")
    def test_intimidation_contest(self):
        result = roll_contest(
            ContestType.INTIMIDATION,
            0,
            _SKILL_LOW,
            _rng=_rng(actor=_ROLL_THIRTEEN, target=_ROLL_EIGHT),
        )
        assert result.contest_type == ContestType.INTIMIDATION
        assert result.outcome == ContestOutcome.ACTOR_SUCCEEDS

    @allure.story("Social contest types")
    @allure.title("Stealth contests pit the actor's stealth against the target's perception")
    def test_stealth_contest(self):
        result = roll_contest(ContestType.STEALTH, 0, _SKILL_HIGH, _rng=_rng(actor=_ROLL_FIVE, target=_ROLL_EIGHTEEN))
        assert result.contest_type == ContestType.STEALTH
        assert result.outcome == ContestOutcome.TARGET_DOMINATES


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestRollContestStatistics:
    """Statistical properties of roll_contest."""

    @allure.story("Statistical properties")
    @allure.title("Contest dice always produce rolls within the valid 1..20 range")
    def test_rolls_in_valid_range(self):
        rng = random.Random(_FUZZ_SEED)
        for _ in range(_FUZZ_ITERATIONS):
            result = roll_contest(ContestType.COMBAT, _SKILL_ZERO, _SKILL_MID, _rng=rng)
            assert 1 <= result.actor_roll <= _D20
            assert 1 <= result.target_roll <= _D20

    @allure.story("Statistical properties")
    @allure.title("Contest rolls produce at least three distinct outcomes across 100 random seeds")
    def test_different_seeds_give_multiple_outcomes(self):
        outcomes = set()
        for seed in range(100):
            result = roll_contest(ContestType.COMBAT, _SKILL_ZERO, _SKILL_MID, _rng=random.Random(seed))
            outcomes.add(result.outcome)
        assert len(outcomes) >= 3

    @allure.story("Statistical properties")
    @allure.title("The actor d20 spans the full 1..20 range — a seeded actor_roll of exactly 1 is reachable")
    def test_actor_roll_can_be_one(self):
        # Seed 31's first randint(1, 20) is 1: proves the actor lower bound is 1, not 2.
        result = roll_contest(ContestType.COMBAT, _SKILL_ZERO, _SKILL_ZERO, _rng=random.Random(_SEED_ACTOR_ONE))
        assert result.actor_roll == 1

    @allure.story("Statistical properties")
    @allure.title("The target d20 spans the full 1..20 range — a seeded target_roll of exactly 1 is reachable")
    def test_target_roll_can_be_one(self):
        # Seed 15's second randint(1, 20) is 1: proves the target lower bound is 1, not 2.
        result = roll_contest(ContestType.COMBAT, _SKILL_ZERO, _SKILL_ZERO, _rng=random.Random(_SEED_TARGET_ONE))
        assert result.target_roll == 1


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestContestRollToDict:
    """contest_roll_to_dict serializes every field under its exact JSON key."""

    @allure.story("Serialization")
    @allure.title("contest_roll_to_dict emits the exact key set with each value placed under the right key")
    def test_serializes_every_field_under_exact_key(self):
        roll = ContestRoll(
            contest_type=ContestType.PERSUASION,
            outcome=ContestOutcome.ACTOR_SUCCEEDS,
            actor_roll=_ROLL_EIGHT,
            target_roll=_ROLL_TWELVE,
            actor_bonus=_SKILL_LOW,
            target_bonus=_SKILL_SEVEN,
        )
        assert contest_roll_to_dict(roll) == {
            "contest_type": "persuasion",
            "outcome": "actor_succeeds",
            "actor_roll": _ROLL_EIGHT,
            "target_roll": _ROLL_TWELVE,
            "actor_bonus": _SKILL_LOW,
            "target_bonus": _SKILL_SEVEN,
            "description": roll.description,
        }
