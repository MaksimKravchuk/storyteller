"""Tests for the generic contest dice system that replaces combat-only dice."""

from __future__ import annotations

import random
from collections.abc import Iterator

import pytest

from cast.dice import (
    CONTEST_SKILL_MAP,
    ContestOutcome,
    ContestRoll,
    ContestType,
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


class TestContestTypeEnum:
    """All expected contest types exist."""

    def test_combat_type(self):
        assert ContestType.COMBAT.value == "combat"

    def test_persuasion_type(self):
        assert ContestType.PERSUASION.value == "persuasion"

    def test_deception_type(self):
        assert ContestType.DECEPTION.value == "deception"

    def test_intimidation_type(self):
        assert ContestType.INTIMIDATION.value == "intimidation"

    def test_stealth_type(self):
        assert ContestType.STEALTH.value == "stealth"

    def test_five_types_total(self):
        assert len(ContestType) == 5


class TestContestOutcomeEnum:
    """All expected contest outcomes exist."""

    def test_actor_dominates(self):
        assert ContestOutcome.ACTOR_DOMINATES.value == "actor_dominates"

    def test_actor_succeeds(self):
        assert ContestOutcome.ACTOR_SUCCEEDS.value == "actor_succeeds"

    def test_target_resists(self):
        assert ContestOutcome.TARGET_RESISTS.value == "target_resists"

    def test_target_dominates(self):
        assert ContestOutcome.TARGET_DOMINATES.value == "target_dominates"

    def test_four_outcomes_total(self):
        assert len(ContestOutcome) == 4


class TestContestSkillMap:
    """CONTEST_SKILL_MAP maps every ContestType to an attribute name."""

    def test_has_all_types(self):
        for ct in ContestType:
            assert ct in CONTEST_SKILL_MAP, f"Missing map entry for {ct}"

    def test_combat_maps_to_combat_skill(self):
        assert CONTEST_SKILL_MAP[ContestType.COMBAT] == "combat_skill"

    def test_persuasion_maps_to_persuasion_skill(self):
        assert CONTEST_SKILL_MAP[ContestType.PERSUASION] == "persuasion_skill"

    def test_deception_maps_to_deception_skill(self):
        assert CONTEST_SKILL_MAP[ContestType.DECEPTION] == "deception_skill"

    def test_intimidation_maps_to_intimidation_skill(self):
        assert CONTEST_SKILL_MAP[ContestType.INTIMIDATION] == "intimidation_skill"

    def test_stealth_maps_to_perception_skill(self):
        assert CONTEST_SKILL_MAP[ContestType.STEALTH] == "perception_skill"


class TestRollContestOutcomes:
    """Outcome classification based on diff = target_total - actor_total."""

    def test_target_dominates_high_diff(self):
        # target total = 18 + 10 = 28, actor total = 5 + 0 = 5, diff = 23
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_HIGH, _rng=_rng(actor=_ROLL_FIVE, target=_ROLL_EIGHTEEN))
        assert result.outcome == ContestOutcome.TARGET_DOMINATES

    def test_target_resists(self):
        # target total = 10 + 5 = 15, actor total = 14 + 0 = 14, diff = 1
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_MID, _rng=_rng(actor=_ROLL_FOURTEEN, target=_ROLL_TEN))
        assert result.outcome == ContestOutcome.TARGET_RESISTS

    def test_actor_succeeds(self):
        # target total = 8 + 2 = 10, actor total = 13 + 0 = 13, diff = -3
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_LOW, _rng=_rng(actor=_ROLL_THIRTEEN, target=_ROLL_EIGHT))
        assert result.outcome == ContestOutcome.ACTOR_SUCCEEDS

    def test_actor_dominates(self):
        # target total = 3 + 0 = 3, actor total = 15 + 0 = 15, diff = -12
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_ZERO, _rng=_rng(actor=_ROLL_FIFTEEN, target=_ROLL_THREE))
        assert result.outcome == ContestOutcome.ACTOR_DOMINATES

    def test_zero_skill_no_bonus(self):
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_ZERO, _rng=_rng(actor=_ROLL_TEN, target=_ROLL_TEN))
        assert result.actor_bonus == 0
        assert result.target_bonus == 0
        assert result.outcome == ContestOutcome.TARGET_RESISTS


class TestRollContestBoundaries:
    """Exact boundary conditions for outcome thresholds."""

    def test_boundary_target_resists_at_zero(self):
        # target total = 10 + 5 = 15, actor total = 15 + 0 = 15, diff = 0
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_MID, _rng=_rng(actor=_ROLL_FIFTEEN, target=_ROLL_TEN))
        assert result.outcome == ContestOutcome.TARGET_RESISTS

    def test_boundary_actor_succeeds_at_minus_one(self):
        # target total = 10 + 5 = 15, actor total = 16 + 0 = 16, diff = -1
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_MID, _rng=_rng(actor=_ROLL_SIXTEEN, target=_ROLL_TEN))
        assert result.outcome == ContestOutcome.ACTOR_SUCCEEDS

    def test_boundary_target_dominates_at_five(self):
        # target total = 10 + 5 = 15, actor total = 10 + 0 = 10, diff = 5
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_MID, _rng=_rng(actor=_ROLL_TEN, target=_ROLL_TEN))
        assert result.outcome == ContestOutcome.TARGET_DOMINATES

    def test_boundary_actor_dominates_at_minus_six(self):
        # target total = 7 + 0 = 7, actor total = 13 + 0 = 13, diff = -6
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_ZERO, _rng=_rng(actor=_ROLL_THIRTEEN, target=_ROLL_SEVEN))
        assert result.outcome == ContestOutcome.ACTOR_DOMINATES


class TestRollContestFields:
    """Roll values are correctly recorded."""

    def test_roll_values_recorded(self):
        result = roll_contest(ContestType.COMBAT, 0, _SKILL_SEVEN, _rng=_rng(actor=_ROLL_EIGHT, target=_ROLL_TWELVE))
        assert result.actor_roll == _ROLL_EIGHT
        assert result.target_roll == _ROLL_TWELVE
        assert result.actor_bonus == 0
        assert result.target_bonus == _SKILL_SEVEN

    def test_contest_type_recorded(self):
        result = roll_contest(ContestType.PERSUASION, 0, _SKILL_MID, _rng=_rng(fixed=_ROLL_TEN))
        assert result.contest_type == ContestType.PERSUASION

    def test_both_bonuses_recorded(self):
        result = roll_contest(ContestType.DECEPTION, 3, _SKILL_MID, _rng=_rng(fixed=_ROLL_TEN))
        assert result.actor_bonus == 3
        assert result.target_bonus == _SKILL_MID


class TestContestRollDescription:
    """Each outcome has a non-empty description."""

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


class TestRollContestSocialTypes:
    """Non-combat contest types work correctly."""

    def test_persuasion_contest(self):
        result = roll_contest(ContestType.PERSUASION, 0, _SKILL_MID, _rng=_rng(actor=_ROLL_FIFTEEN, target=_ROLL_TEN))
        assert result.contest_type == ContestType.PERSUASION
        assert result.outcome == ContestOutcome.TARGET_RESISTS

    def test_deception_contest(self):
        result = roll_contest(ContestType.DECEPTION, 0, _SKILL_ZERO, _rng=_rng(actor=_ROLL_FIFTEEN, target=_ROLL_THREE))
        assert result.contest_type == ContestType.DECEPTION
        assert result.outcome == ContestOutcome.ACTOR_DOMINATES

    def test_intimidation_contest(self):
        result = roll_contest(
            ContestType.INTIMIDATION, 0, _SKILL_LOW, _rng=_rng(actor=_ROLL_THIRTEEN, target=_ROLL_EIGHT),
        )
        assert result.contest_type == ContestType.INTIMIDATION
        assert result.outcome == ContestOutcome.ACTOR_SUCCEEDS

    def test_stealth_contest(self):
        result = roll_contest(ContestType.STEALTH, 0, _SKILL_HIGH, _rng=_rng(actor=_ROLL_FIVE, target=_ROLL_EIGHTEEN))
        assert result.contest_type == ContestType.STEALTH
        assert result.outcome == ContestOutcome.TARGET_DOMINATES


class TestRollContestStatistics:
    """Statistical properties of roll_contest."""

    def test_rolls_in_valid_range(self):
        rng = random.Random(_FUZZ_SEED)
        for _ in range(_FUZZ_ITERATIONS):
            result = roll_contest(ContestType.COMBAT, _SKILL_ZERO, _SKILL_MID, _rng=rng)
            assert 1 <= result.actor_roll <= _D20
            assert 1 <= result.target_roll <= _D20

    def test_different_seeds_give_multiple_outcomes(self):
        outcomes = set()
        for seed in range(100):
            result = roll_contest(ContestType.COMBAT, _SKILL_ZERO, _SKILL_MID, _rng=random.Random(seed))
            outcomes.add(result.outcome)
        assert len(outcomes) >= 3
