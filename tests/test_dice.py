"""Tests for combat dice mechanics."""

from __future__ import annotations

import random


from cast.dice import (
    AGGRESSION_THRESHOLDS,
    CombatOutcome,
    CombatRoll,
    roll_aggression,
    roll_combat,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HOSTILE = "hostile"
_EIGHTEEN = 18
_FOURTEEN = 14
_THIRTEEN = 13
_FIFTEEN = 15
_SIXTEEN = 16
_TWELVE = 12
_SEED = 12345
_SAMPLE_SIZE = 200
_D20 = 20
_LOW_ATTACK_RATE = 700
_HIGH_ATTACK_RATE = 900


class TestCombatOutcomes:
    def test_npc_overpowers_high_skill_high_roll(self):
        """NPC with high combat_skill and high roll should overpower."""
        # Force specific rolls: we'll try many seeds to find one
        # Instead, test with known math: npc_roll+bonus - player_roll >= 5
        combat_roll = roll_combat(10, _rng=_fixed_rng(npc=_EIGHTEEN, player=5))
        assert combat_roll.outcome == CombatOutcome.NPC_OVERPOWERS

    def test_npc_defends(self):
        """NPC total >= player roll but < player+5 → NPC_DEFENDS."""
        combat_roll = roll_combat(5, _rng=_fixed_rng(npc=10, player=_FOURTEEN))
        # npc_total = 10+5 = 15, diff = 15-14 = 1 >= 0 → NPC_DEFENDS
        assert combat_roll.outcome == CombatOutcome.NPC_DEFENDS

    def test_player_succeeds(self):
        """Player roll > NPC total but by less than 5 → PLAYER_SUCCEEDS."""
        combat_roll = roll_combat(2, _rng=_fixed_rng(npc=8, player=_THIRTEEN))
        # npc_total = 8+2 = 10, diff = 10-13 = -3 → PLAYER_SUCCEEDS
        assert combat_roll.outcome == CombatOutcome.PLAYER_SUCCEEDS

    def test_player_dominates(self):
        """Player roll > NPC total by 6+ → PLAYER_DOMINATES."""
        combat_roll = roll_combat(0, _rng=_fixed_rng(npc=3, player=_FIFTEEN))
        # npc_total = 3+0 = 3, diff = 3-15 = -12 → PLAYER_DOMINATES
        assert combat_roll.outcome == CombatOutcome.PLAYER_DOMINATES


class TestCombatOutcomeBoundaries:
    def test_exact_boundary_npc_defends(self):
        """diff == 0 → NPC_DEFENDS (tie goes to NPC)."""
        combat_roll = roll_combat(5, _rng=_fixed_rng(npc=10, player=_FIFTEEN))
        # npc_total = 15, diff = 0 → NPC_DEFENDS
        assert combat_roll.outcome == CombatOutcome.NPC_DEFENDS

    def test_exact_boundary_player_succeeds(self):
        """diff == -1 → PLAYER_SUCCEEDS."""
        combat_roll = roll_combat(5, _rng=_fixed_rng(npc=10, player=_SIXTEEN))
        # npc_total = 15, diff = -1 → PLAYER_SUCCEEDS
        assert combat_roll.outcome == CombatOutcome.PLAYER_SUCCEEDS

    def test_exact_boundary_npc_overpowers(self):
        """diff == 5 → NPC_OVERPOWERS."""
        combat_roll = roll_combat(5, _rng=_fixed_rng(npc=10, player=10))
        # npc_total = 15, diff = 5 → NPC_OVERPOWERS
        assert combat_roll.outcome == CombatOutcome.NPC_OVERPOWERS

    def test_exact_boundary_player_dominates(self):
        """diff == -6 → PLAYER_DOMINATES."""
        combat_roll = roll_combat(0, _rng=_fixed_rng(npc=7, player=_THIRTEEN))
        # npc_total = 7, diff = -6 → PLAYER_DOMINATES
        assert combat_roll.outcome == CombatOutcome.PLAYER_DOMINATES


class TestCombatRollFields:
    def test_roll_values_recorded(self):
        combat_roll = roll_combat(7, _rng=_fixed_rng(npc=_TWELVE, player=8))
        assert combat_roll.npc_roll == _TWELVE
        assert combat_roll.player_roll == 8
        assert combat_roll.npc_bonus == 7

    def test_description_not_empty(self):
        for outcome in CombatOutcome:
            roll = CombatRoll(
                outcome=outcome,
                npc_roll=10,
                player_roll=10,
                npc_bonus=0,
            )
            assert len(roll.description) > 0


class TestRollRandomness:
    def test_rolls_in_valid_range(self):
        """All rolls should be 1-20."""
        rng = random.Random(_SEED)
        for _ in range(_SAMPLE_SIZE):
            combat_roll = roll_combat(5, _rng=rng)
            assert 1 <= combat_roll.player_roll <= _D20
            assert 1 <= combat_roll.npc_roll <= _D20

    def test_different_seeds_different_outcomes(self):
        """With enough rolls, we should see multiple outcomes."""
        outcomes = set()
        for seed in range(100):
            combat_roll = roll_combat(5, _rng=random.Random(seed))
            outcomes.add(combat_roll.outcome)
        assert len(outcomes) >= 3


class TestZeroCombatSkill:
    def test_zero_skill_no_bonus(self):
        combat_roll = roll_combat(0, _rng=_fixed_rng(npc=10, player=10))
        assert combat_roll.npc_bonus == 0
        # npc_total = 10, diff = 0 → NPC_DEFENDS
        assert combat_roll.outcome == CombatOutcome.NPC_DEFENDS


# ---------------------------------------------------------------------------
# Aggression roll
# ---------------------------------------------------------------------------


class TestAggressionRollOutcomes:
    def test_hostile_low_threshold(self):
        """Hostile mood: threshold is 5, roll of 5 should attack."""
        aggression_roll = roll_aggression(_HOSTILE, _rng=_single_rng(5))
        assert aggression_roll is not None
        assert aggression_roll.will_attack is True
        assert aggression_roll.threshold == 5

    def test_hostile_below_threshold(self):
        """Hostile mood: roll of 4 should not attack."""
        aggression_roll = roll_aggression(_HOSTILE, _rng=_single_rng(4))
        assert aggression_roll is not None
        assert aggression_roll.will_attack is False

    def test_enraged_very_low_threshold(self):
        """Enraged mood: threshold is 3, roll of 3 should attack."""
        aggression_roll = roll_aggression("enraged", _rng=_single_rng(3))
        assert aggression_roll is not None
        assert aggression_roll.will_attack is True
        assert aggression_roll.threshold == 3

    def test_angry_threshold(self):
        aggression_roll = roll_aggression("angry", _rng=_single_rng(8))
        assert aggression_roll is not None
        assert aggression_roll.will_attack is True
        assert aggression_roll.threshold == 8

    def test_angry_below_threshold(self):
        aggression_roll = roll_aggression("angry", _rng=_single_rng(7))
        assert aggression_roll is not None
        assert aggression_roll.will_attack is False

    def test_peaceful_mood_returns_none(self):
        """Moods not in threshold table should return None."""
        assert roll_aggression("neutral") is None
        assert roll_aggression("calm") is None
        assert roll_aggression("happy") is None

    def test_case_insensitive(self):
        aggression_roll = roll_aggression("HOSTILE", _rng=_single_rng(5))
        assert aggression_roll is not None
        assert aggression_roll.will_attack is True


class TestAggressionRollProperties:
    def test_all_thresholds_have_valid_values(self):
        for mood, threshold in AGGRESSION_THRESHOLDS.items():
            assert 1 <= threshold <= _D20, f"{mood} has invalid threshold {threshold}"

    def test_hostile_high_attack_rate(self):
        """Hostile (threshold 5): 16/20 = 80% chance to attack."""
        rngs = [random.Random(seed) for seed in range(1000)]
        rolls = [roll_aggression(_HOSTILE, _rng=rng) for rng in rngs]
        attacks = sum(1 for roll in rolls if roll.will_attack)
        # Should be roughly 80%, allow wide margin
        assert _LOW_ATTACK_RATE < attacks < _HIGH_ATTACK_RATE

    def test_aggression_roll_fields(self):
        aggression_roll = roll_aggression(_HOSTILE, _rng=_single_rng(_TWELVE))
        assert aggression_roll.roll == _TWELVE
        assert aggression_roll.mood == _HOSTILE
        assert aggression_roll.threshold == 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FixedRng:
    """Fake RNG yielding player_roll first, then npc_roll."""

    def __init__(self, player: int, npc: int):
        self._calls = iter([player, npc])

    def randint(self, low: int, high: int) -> int:
        return next(self._calls)


class _SingleRng:
    """Fake RNG that always yields the same value."""

    def __init__(self, fixed_roll: int):
        self._fixed_roll = fixed_roll

    def randint(self, low: int, high: int) -> int:
        return self._fixed_roll


def _fixed_rng(*, npc: int, player: int) -> random.Random:
    """Return a fake RNG that yields player_roll first, then npc_roll.

    ``roll_combat`` calls rng.randint twice: first for player, then for NPC.
    """
    return _FixedRng(player, npc)  # type: ignore[return-value]


def _single_rng(fixed_roll: int) -> random.Random:
    """Return a fake RNG that always yields *fixed_roll*."""
    return _SingleRng(fixed_roll)  # type: ignore[return-value]
