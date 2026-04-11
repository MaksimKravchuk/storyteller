"""Tests for combat dice mechanics."""

from __future__ import annotations

import random
from collections.abc import Iterator

import allure

from cast.dice import (
    AGGRESSION_THRESHOLDS,
    CombatOutcome,
    CombatRoll,
    roll_aggression,
    roll_combat,
)

_HOSTILE = "hostile"
_D20 = 20

_NPC_SKILL_HIGH = 10
_NPC_SKILL_MID = 5
_NPC_SKILL_LOW = 2
_NPC_SKILL_ZERO = 0
_NPC_SKILL_SEVEN = 7

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

_ATTACK_RATE_LOW = 700
_ATTACK_RATE_HIGH = 900

_HOSTILE_THRESHOLD = 5
_ENRAGED_THRESHOLD = 3


class _FakeRng:
    """Fake RNG for deterministic dice tests.

    When given both *npc* and *player*, yields player first then npc.
    When given only *fixed*, always returns that value.
    """

    def __init__(
        self,
        *,
        npc: int | None = None,
        player: int | None = None,
        fixed: int | None = None,
    ) -> None:
        if fixed is None:
            rolls: list[int] = [player or 0, npc or 0]
        else:
            rolls = [fixed, fixed]
        self._calls: Iterator[int] = iter(rolls)

    def randint(self, low: int, high: int) -> int:
        return next(self._calls)


def _rng(
    *,
    npc: int | None = None,
    player: int | None = None,
    fixed: int | None = None,
) -> random.Random:
    """Build a ``_FakeRng`` cast to ``random.Random``."""
    return _FakeRng(npc=npc, player=player, fixed=fixed)  # type: ignore[return-value]


@allure.epic("Combat & Action Resolution")
@allure.feature("Combat dice")
class TestCombatOutcomeCategories:
    """Tests for basic combat outcome classification."""

    @allure.story("Outcome categories")
    @allure.title("NPC with +10 skill rolling 18 vs player 5 is classified as NPC_OVERPOWERS")
    def test_npc_overpowers(self):
        combat_roll = roll_combat(_NPC_SKILL_HIGH, _rng=_rng(npc=_ROLL_EIGHTEEN, player=_ROLL_FIVE))
        assert combat_roll.outcome == CombatOutcome.NPC_OVERPOWERS

    @allure.story("Outcome categories")
    @allure.title("NPC holding a small edge over the player is classified as NPC_DEFENDS")
    def test_npc_defends(self):
        combat_roll = roll_combat(_NPC_SKILL_MID, _rng=_rng(npc=_ROLL_TEN, player=_ROLL_FOURTEEN))
        assert combat_roll.outcome == CombatOutcome.NPC_DEFENDS

    @allure.story("Outcome categories")
    @allure.title("Player winning by a modest margin is classified as PLAYER_SUCCEEDS")
    def test_player_succeeds(self):
        combat_roll = roll_combat(_NPC_SKILL_LOW, _rng=_rng(npc=_ROLL_EIGHT, player=_ROLL_THIRTEEN))
        assert combat_roll.outcome == CombatOutcome.PLAYER_SUCCEEDS

    @allure.story("Outcome categories")
    @allure.title("Player winning by a large margin against an unskilled NPC is PLAYER_DOMINATES")
    def test_player_dominates(self):
        combat_roll = roll_combat(_NPC_SKILL_ZERO, _rng=_rng(npc=_ROLL_THREE, player=_ROLL_FIFTEEN))
        assert combat_roll.outcome == CombatOutcome.PLAYER_DOMINATES

    @allure.story("Outcome categories")
    @allure.title("Every combat outcome category has a human-readable description attached")
    def test_description_not_empty(self):
        for outcome in CombatOutcome:
            roll = CombatRoll(outcome=outcome, npc_roll=_ROLL_TEN, player_roll=_ROLL_TEN, npc_bonus=0)
            assert len(roll.description) > 0

    @allure.story("Outcome categories")
    @allure.title("An unskilled NPC tying the player's roll falls back to NPC_DEFENDS with zero bonus")
    def test_zero_skill_no_bonus(self):
        combat_roll = roll_combat(_NPC_SKILL_ZERO, _rng=_rng(npc=_ROLL_TEN, player=_ROLL_TEN))
        assert combat_roll.npc_bonus == 0
        assert combat_roll.outcome == CombatOutcome.NPC_DEFENDS


@allure.epic("Combat & Action Resolution")
@allure.feature("Combat dice")
class TestCombatBoundariesAndStats:
    """Tests for boundary conditions, recorded values, and statistical properties."""

    @allure.story("Boundary conditions")
    @allure.title("Combat outcome at exactly the NPC_DEFENDS / PLAYER_SUCCEEDS boundary resolves to NPC_DEFENDS")
    def test_boundary_npc_defends_at_zero(self):
        combat_roll = roll_combat(_NPC_SKILL_MID, _rng=_rng(npc=_ROLL_TEN, player=_ROLL_FIFTEEN))
        assert combat_roll.outcome == CombatOutcome.NPC_DEFENDS

    @allure.story("Boundary conditions")
    @allure.title("One point past the NPC_DEFENDS boundary flips the outcome to PLAYER_SUCCEEDS")
    def test_boundary_player_succeeds_at_minus_one(self):
        combat_roll = roll_combat(_NPC_SKILL_MID, _rng=_rng(npc=_ROLL_TEN, player=_ROLL_SIXTEEN))
        assert combat_roll.outcome == CombatOutcome.PLAYER_SUCCEEDS

    @allure.story("Boundary conditions")
    @allure.title("NPC winning by exactly five with skill bonus is classified as NPC_OVERPOWERS")
    def test_boundary_npc_overpowers_at_five(self):
        combat_roll = roll_combat(_NPC_SKILL_MID, _rng=_rng(npc=_ROLL_TEN, player=_ROLL_TEN))
        assert combat_roll.outcome == CombatOutcome.NPC_OVERPOWERS

    @allure.story("Boundary conditions")
    @allure.title("Player winning by six or more against an unskilled NPC is classified as PLAYER_DOMINATES")
    def test_boundary_player_dominates_at_minus_six(self):
        combat_roll = roll_combat(_NPC_SKILL_ZERO, _rng=_rng(npc=_ROLL_SEVEN, player=_ROLL_THIRTEEN))
        assert combat_roll.outcome == CombatOutcome.PLAYER_DOMINATES

    @allure.story("Recorded values")
    @allure.title("CombatRoll records the raw NPC roll, player roll, and skill bonus on the result object")
    def test_roll_values_recorded(self):
        combat_roll = roll_combat(_NPC_SKILL_SEVEN, _rng=_rng(npc=_ROLL_TWELVE, player=_ROLL_EIGHT))
        assert combat_roll.npc_roll == _ROLL_TWELVE
        assert combat_roll.player_roll == _ROLL_EIGHT
        assert combat_roll.npc_bonus == _NPC_SKILL_SEVEN

    @allure.story("Statistical properties")
    @allure.title("All d20 dice rolls fall within the valid 1..20 range across many samples")
    def test_rolls_in_valid_range(self):
        rng = random.Random(_FUZZ_SEED)
        for _ in range(_FUZZ_ITERATIONS):
            combat_roll = roll_combat(_NPC_SKILL_MID, _rng=rng)
            assert 1 <= combat_roll.player_roll <= _D20
            assert 1 <= combat_roll.npc_roll <= _D20

    @allure.story("Statistical properties")
    @allure.title("Combat rolls produce at least three distinct outcomes across 100 random seeds")
    def test_different_seeds_give_multiple_outcomes(self):
        outcomes = set()
        for seed in range(100):
            outcomes.add(roll_combat(_NPC_SKILL_MID, _rng=random.Random(seed)).outcome)
        assert len(outcomes) >= 3


@allure.epic("Combat & Action Resolution")
@allure.feature("Combat dice")
class TestAggressionRollBasic:
    """Tests for basic aggression roll mechanics."""

    @allure.story("Aggression roll")
    @allure.title("Hostile NPC rolls at or under the threshold and is flagged as will_attack")
    def test_hostile_low_threshold(self):
        agg = roll_aggression(_HOSTILE, _rng=_rng(fixed=_ROLL_FIVE))
        assert agg is not None
        assert agg.will_attack is True
        assert agg.threshold == _HOSTILE_THRESHOLD

    @allure.story("Aggression roll")
    @allure.title("Hostile NPC rolling just above the threshold declines to attack")
    def test_hostile_below_threshold(self):
        agg = roll_aggression(_HOSTILE, _rng=_rng(fixed=4))
        assert agg is not None
        assert agg.will_attack is False

    @allure.story("Aggression roll")
    @allure.title("Enraged mood uses a lower aggression threshold than hostile")
    def test_enraged_threshold(self):
        agg = roll_aggression("enraged", _rng=_rng(fixed=_ROLL_THREE))
        assert agg is not None
        assert agg.will_attack is True
        assert agg.threshold == _ENRAGED_THRESHOLD

    @allure.story("Aggression roll")
    @allure.title("Angry mood will attack when the d20 roll lands at or under the angry threshold")
    def test_angry_threshold(self):
        agg = roll_aggression("angry", _rng=_rng(fixed=_ROLL_EIGHT))
        assert agg is not None
        assert agg.will_attack is True

    @allure.story("Aggression roll")
    @allure.title("Angry mood rolling above the threshold holds back from attacking")
    def test_angry_below_threshold(self):
        agg = roll_aggression("angry", _rng=_rng(fixed=_ROLL_SEVEN))
        assert agg is not None
        assert agg.will_attack is False

    @allure.story("Aggression roll")
    @allure.title("Peaceful moods (neutral, calm, happy) do not trigger an aggression roll at all")
    def test_peaceful_mood_returns_none(self):
        assert roll_aggression("neutral") is None
        assert roll_aggression("calm") is None
        assert roll_aggression("happy") is None

    @allure.story("Aggression roll")
    @allure.title("Mood matching for aggression rolls is case-insensitive")
    def test_case_insensitive(self):
        agg = roll_aggression("HOSTILE", _rng=_rng(fixed=_ROLL_FIVE))
        assert agg is not None
        assert agg.will_attack is True


@allure.epic("Combat & Action Resolution")
@allure.feature("Combat dice")
class TestAggressionRollProperties:
    """Tests for aggression roll thresholds and statistical properties."""

    @allure.story("Aggression thresholds")
    @allure.title("Every mood in the AGGRESSION_THRESHOLDS table has a threshold in the valid 1..20 range")
    def test_all_thresholds_valid(self):
        for mood, threshold in AGGRESSION_THRESHOLDS.items():
            assert 1 <= threshold <= _D20, f"{mood} has invalid threshold {threshold}"

    @allure.story("Aggression thresholds")
    @allure.title("Across 1000 random rolls a hostile NPC attacks between 70% and 90% of the time")
    def test_hostile_high_attack_rate(self):
        rngs = [random.Random(seed) for seed in range(1000)]
        rolls = [roll_aggression(_HOSTILE, _rng=rng) for rng in rngs]
        attacks = sum(1 for roll in rolls if roll.will_attack)
        assert _ATTACK_RATE_LOW < attacks < _ATTACK_RATE_HIGH

    @allure.story("Aggression thresholds")
    @allure.title("AggressionRoll records the raw roll, the mood, and the threshold used for classification")
    def test_aggression_roll_fields(self):
        agg = roll_aggression(_HOSTILE, _rng=_rng(fixed=_ROLL_TWELVE))
        assert agg.roll == _ROLL_TWELVE
        assert agg.mood == _HOSTILE
        assert agg.threshold == _HOSTILE_THRESHOLD
