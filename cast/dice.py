"""Dice-based combat resolution for NPC interactions."""

from __future__ import annotations

import random
import types
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Aggression thresholds — minimum d20 roll for an NPC to retaliate.
# Lower = more likely to attack.  Mood not listed here → no retaliation.
# ---------------------------------------------------------------------------

AGGRESSION_THRESHOLDS: types.MappingProxyType[str, int] = types.MappingProxyType(
    {
        "hostile": 5,
        "enraged": 3,
        "furious": 3,
        "angry": 8,
        "threatened": 10,
        "irritated": 13,
        "suspicious": 15,
    }
)


class CombatOutcome(Enum):
    """Possible outcomes of an NPC vs player combat roll."""

    NPC_OVERPOWERS = "npc_overpowers"
    NPC_DEFENDS = "npc_defends"
    PLAYER_SUCCEEDS = "player_succeeds"
    PLAYER_DOMINATES = "player_dominates"


@dataclass(frozen=True)
class CombatRoll:
    """Result of a combat dice roll."""

    outcome: CombatOutcome
    npc_roll: int
    player_roll: int
    npc_bonus: int

    @property
    def description(self) -> str:
        """Human-readable description of the outcome for prompt injection."""
        descs = {
            CombatOutcome.NPC_OVERPOWERS: (
                "The NPC overpowers the player — they counterattack, pin them down, or deliver a decisive blow."
            ),
            CombatOutcome.NPC_DEFENDS: (
                "The NPC successfully defends — they block the attack, shove the player back, or dodge and retaliate."
            ),
            CombatOutcome.PLAYER_SUCCEEDS: (
                "The player's attack lands — the NPC takes a hit, stumbles, loses their weapon, or is knocked back."
            ),
            CombatOutcome.PLAYER_DOMINATES: (
                "The player completely overwhelms the NPC — a devastating "
                "blow, the NPC is knocked out, disarmed, or badly hurt."
            ),
        }
        return descs[self.outcome]


@dataclass(frozen=True)
class AggressionRoll:
    """Result of an NPC aggression check after mood change."""

    will_attack: bool
    roll: int
    threshold: int
    mood: str


def roll_aggression(mood: str, _rng: random.Random | None = None) -> AggressionRoll | None:
    """Roll 1d20 to decide whether an NPC with *mood* retaliates.

    Returns ``None`` when the mood has no aggression threshold (peaceful moods).
    Otherwise returns an ``AggressionRoll`` with the decision.
    """
    threshold = AGGRESSION_THRESHOLDS.get(mood.lower())
    if threshold is None:
        return None
    rng = _rng or random.Random()
    roll = rng.randint(1, 20)
    return AggressionRoll(
        will_attack=roll >= threshold,
        roll=roll,
        threshold=threshold,
        mood=mood.lower(),
    )


def roll_combat(npc_combat_skill: int, _rng: random.Random | None = None) -> CombatRoll:
    """Roll 1d20 for each side, add NPC combat_skill bonus, determine outcome.

    ``npc_combat_skill`` should be 0-10 (from NPC attributes).
    A higher skill gives the NPC a bigger bonus on their roll.

    Outcome thresholds (NPC total vs player roll):
    - NPC total >= player roll + 5  → NPC_OVERPOWERS
    - NPC total >= player roll      → NPC_DEFENDS
    - NPC total >= player roll - 5  → PLAYER_SUCCEEDS
    - NPC total <  player roll - 5  → PLAYER_DOMINATES
    """
    rng = _rng or random.Random()
    player_roll = rng.randint(1, 20)
    npc_roll = rng.randint(1, 20)
    npc_total = npc_roll + npc_combat_skill

    diff = npc_total - player_roll

    if diff >= 5:
        outcome = CombatOutcome.NPC_OVERPOWERS
    elif diff >= 0:
        outcome = CombatOutcome.NPC_DEFENDS
    elif diff >= -5:
        outcome = CombatOutcome.PLAYER_SUCCEEDS
    else:
        outcome = CombatOutcome.PLAYER_DOMINATES

    return CombatRoll(
        outcome=outcome,
        npc_roll=npc_roll,
        player_roll=player_roll,
        npc_bonus=npc_combat_skill,
    )
