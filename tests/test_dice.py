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


class TestCombatOutcomes:
    def test_npc_overpowers_high_skill_high_roll(self):
        """NPC with high combat_skill and high roll should overpower."""
        # Force specific rolls: we'll try many seeds to find one
        # Instead, test with known math: npc_roll+bonus - player_roll >= 5
        result = roll_combat(10, _rng=_fixed_rng(npc=18, player=5))
        assert result.outcome == CombatOutcome.NPC_OVERPOWERS

    def test_npc_defends(self):
        """NPC total >= player roll but < player+5 → NPC_DEFENDS."""
        result = roll_combat(5, _rng=_fixed_rng(npc=10, player=14))
        # npc_total = 10+5 = 15, diff = 15-14 = 1 >= 0 → NPC_DEFENDS
        assert result.outcome == CombatOutcome.NPC_DEFENDS

    def test_player_succeeds(self):
        """Player roll > NPC total but by less than 5 → PLAYER_SUCCEEDS."""
        result = roll_combat(2, _rng=_fixed_rng(npc=8, player=13))
        # npc_total = 8+2 = 10, diff = 10-13 = -3 → PLAYER_SUCCEEDS
        assert result.outcome == CombatOutcome.PLAYER_SUCCEEDS

    def test_player_dominates(self):
        """Player roll > NPC total by 6+ → PLAYER_DOMINATES."""
        result = roll_combat(0, _rng=_fixed_rng(npc=3, player=15))
        # npc_total = 3+0 = 3, diff = 3-15 = -12 → PLAYER_DOMINATES
        assert result.outcome == CombatOutcome.PLAYER_DOMINATES

    def test_exact_boundary_npc_defends(self):
        """diff == 0 → NPC_DEFENDS (tie goes to NPC)."""
        result = roll_combat(5, _rng=_fixed_rng(npc=10, player=15))
        # npc_total = 15, diff = 0 → NPC_DEFENDS
        assert result.outcome == CombatOutcome.NPC_DEFENDS

    def test_exact_boundary_player_succeeds(self):
        """diff == -1 → PLAYER_SUCCEEDS."""
        result = roll_combat(5, _rng=_fixed_rng(npc=10, player=16))
        # npc_total = 15, diff = -1 → PLAYER_SUCCEEDS
        assert result.outcome == CombatOutcome.PLAYER_SUCCEEDS

    def test_exact_boundary_npc_overpowers(self):
        """diff == 5 → NPC_OVERPOWERS."""
        result = roll_combat(5, _rng=_fixed_rng(npc=10, player=10))
        # npc_total = 15, diff = 5 → NPC_OVERPOWERS
        assert result.outcome == CombatOutcome.NPC_OVERPOWERS

    def test_exact_boundary_player_dominates(self):
        """diff == -6 → PLAYER_DOMINATES."""
        result = roll_combat(0, _rng=_fixed_rng(npc=7, player=13))
        # npc_total = 7, diff = -6 → PLAYER_DOMINATES
        assert result.outcome == CombatOutcome.PLAYER_DOMINATES


class TestCombatRollFields:
    def test_roll_values_recorded(self):
        result = roll_combat(7, _rng=_fixed_rng(npc=12, player=8))
        assert result.npc_roll == 12
        assert result.player_roll == 8
        assert result.npc_bonus == 7

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
        rng = random.Random(12345)
        for _ in range(200):
            result = roll_combat(5, _rng=rng)
            assert 1 <= result.player_roll <= 20
            assert 1 <= result.npc_roll <= 20

    def test_different_seeds_different_outcomes(self):
        """With enough rolls, we should see multiple outcomes."""
        outcomes = set()
        for seed in range(100):
            result = roll_combat(5, _rng=random.Random(seed))
            outcomes.add(result.outcome)
        assert len(outcomes) >= 3


class TestZeroCombatSkill:
    def test_zero_skill_no_bonus(self):
        result = roll_combat(0, _rng=_fixed_rng(npc=10, player=10))
        assert result.npc_bonus == 0
        # npc_total = 10, diff = 0 → NPC_DEFENDS
        assert result.outcome == CombatOutcome.NPC_DEFENDS


# ---------------------------------------------------------------------------
# Aggression roll
# ---------------------------------------------------------------------------


class TestAggressionRoll:
    def test_hostile_low_threshold(self):
        """Hostile mood: threshold is 5, roll of 5 should attack."""
        result = roll_aggression("hostile", _rng=_single_rng(5))
        assert result is not None
        assert result.will_attack is True
        assert result.threshold == 5

    def test_hostile_below_threshold(self):
        """Hostile mood: roll of 4 should not attack."""
        result = roll_aggression("hostile", _rng=_single_rng(4))
        assert result is not None
        assert result.will_attack is False

    def test_enraged_very_low_threshold(self):
        """Enraged mood: threshold is 3, roll of 3 should attack."""
        result = roll_aggression("enraged", _rng=_single_rng(3))
        assert result is not None
        assert result.will_attack is True
        assert result.threshold == 3

    def test_angry_threshold(self):
        result = roll_aggression("angry", _rng=_single_rng(8))
        assert result is not None
        assert result.will_attack is True
        assert result.threshold == 8

    def test_angry_below_threshold(self):
        result = roll_aggression("angry", _rng=_single_rng(7))
        assert result is not None
        assert result.will_attack is False

    def test_peaceful_mood_returns_none(self):
        """Moods not in threshold table should return None."""
        assert roll_aggression("neutral") is None
        assert roll_aggression("calm") is None
        assert roll_aggression("happy") is None

    def test_case_insensitive(self):
        result = roll_aggression("HOSTILE", _rng=_single_rng(5))
        assert result is not None
        assert result.will_attack is True

    def test_all_thresholds_have_valid_values(self):
        for mood, threshold in AGGRESSION_THRESHOLDS.items():
            assert 1 <= threshold <= 20, f"{mood} has invalid threshold {threshold}"

    def test_hostile_high_attack_rate(self):
        """Hostile (threshold 5): 16/20 = 80% chance to attack."""
        attacks = sum(1 for seed in range(1000) if roll_aggression("hostile", _rng=random.Random(seed)).will_attack)
        # Should be roughly 80%, allow wide margin
        assert 700 < attacks < 900

    def test_aggression_roll_fields(self):
        result = roll_aggression("hostile", _rng=_single_rng(12))
        assert result.roll == 12
        assert result.mood == "hostile"
        assert result.threshold == 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fixed_rng(*, npc: int, player: int) -> random.Random:
    """Return a fake RNG that yields player_roll first, then npc_roll.

    ``roll_combat`` calls rng.randint twice: first for player, then for NPC.
    """

    class _FixedRng:
        def __init__(self):
            self._calls = iter([player, npc])

        def randint(self, a: int, b: int) -> int:
            return next(self._calls)

    return _FixedRng()  # type: ignore[return-value]


def _single_rng(value: int) -> random.Random:
    """Return a fake RNG that always yields *value*."""

    class _SingleRng:
        def randint(self, a: int, b: int) -> int:
            return value

    return _SingleRng()  # type: ignore[return-value]
