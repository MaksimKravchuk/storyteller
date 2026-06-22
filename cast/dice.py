"""Dice-based contest resolution for player and NPC interactions.

Provides a generic contest system (d20 + bonus vs d20 + bonus) for combat,
persuasion, deception, intimidation, and stealth.  Also provides an
aggression-check mechanic for NPC mood-based retaliation.
"""

from __future__ import annotations

import contextvars
import random
import types
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from llm.turn_event_logger import record_turn_event


_D20 = 20

# Optionally-installed default RNG for dice rolls. Production never sets it,
# so dice fall back to a fresh ``random.Random()`` per roll — identical to the
# original behaviour. The benchmark harness installs a seeded RNG (per scenario
# + iteration) so contest outcomes reproduce run-to-run, keeping dice luck out
# of the previous-vs-current comparison. A ``ContextVar`` matches the codebase's
# swappable-process-state precedent (see ``llm/turn_event_logger.py``).
_default_rng: contextvars.ContextVar[random.Random | None] = contextvars.ContextVar(
    "dice_default_rng",
    default=None,
)


def set_default_rng(rng: random.Random | None) -> None:
    """Install (or clear, with ``None``) the default RNG for all dice rolls.

    Harness-only seam: the benchmark runner seeds this before each scenario
    iteration. Production code never calls it, so dice stay unseeded.
    """
    _default_rng.set(rng)


def _active_rng() -> random.Random:
    return _default_rng.get() or random.Random()


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

# ---------------------------------------------------------------------------
# Contest system — replaces the old combat-only dice
# ---------------------------------------------------------------------------


class ContestType(Enum):
    """Categories of contested actions."""

    COMBAT = "combat"
    PERSUASION = "persuasion"
    DECEPTION = "deception"
    INTIMIDATION = "intimidation"
    STEALTH = "stealth"


class ContestOutcome(Enum):
    """Possible outcomes of a contested roll.

    Determined by ``diff = target_total - actor_total``:
    - diff >= 5   → TARGET_DOMINATES
    - 0 <= diff < 5   → TARGET_RESISTS
    - -5 <= diff < 0  → ACTOR_SUCCEEDS
    - diff < -5   → ACTOR_DOMINATES
    """

    ACTOR_DOMINATES = "actor_dominates"
    ACTOR_SUCCEEDS = "actor_succeeds"
    TARGET_RESISTS = "target_resists"
    TARGET_DOMINATES = "target_dominates"


# Maps ContestType → (actor_skill_attr, target_skill_attr).
# For most types both sides use the same skill; for STEALTH the actor
# uses stealth_skill while the target defends with perception_skill.
CONTEST_SKILL_MAP: types.MappingProxyType[ContestType, tuple[str, str]] = types.MappingProxyType(
    {
        ContestType.COMBAT: ("combat_skill", "combat_skill"),
        ContestType.PERSUASION: ("persuasion_skill", "persuasion_skill"),
        ContestType.DECEPTION: ("deception_skill", "deception_skill"),
        ContestType.INTIMIDATION: ("intimidation_skill", "intimidation_skill"),
        ContestType.STEALTH: ("stealth_skill", "perception_skill"),
    }
)

_COMBAT_DESCRIPTIONS: types.MappingProxyType[ContestOutcome, str] = types.MappingProxyType(
    {
        ContestOutcome.TARGET_DOMINATES: (
            "The target overpowers the attacker — they counterattack, pin them down, or deliver a decisive blow."
        ),
        ContestOutcome.TARGET_RESISTS: (
            "The target successfully defends — they block the attack, shove the attacker back, or dodge and retaliate."
        ),
        ContestOutcome.ACTOR_SUCCEEDS: (
            "The attacker's strike lands — the target takes a hit, stumbles, loses their weapon, or is knocked back."
        ),
        ContestOutcome.ACTOR_DOMINATES: (
            "The attacker completely overwhelms the target — a devastating "
            "blow, the target is knocked out, disarmed, or badly hurt."
        ),
    }
)

_SOCIAL_DESCRIPTIONS: types.MappingProxyType[ContestOutcome, str] = types.MappingProxyType(
    {
        ContestOutcome.TARGET_DOMINATES: (
            "The target sees through the attempt completely and turns it against the actor."
        ),
        ContestOutcome.TARGET_RESISTS: ("The target resists — they are unconvinced, suspicious, or unmoved."),
        ContestOutcome.ACTOR_SUCCEEDS: (
            "The actor's attempt partially works — the target is swayed, fooled, or shaken, but not fully."
        ),
        ContestOutcome.ACTOR_DOMINATES: (
            "The actor's attempt succeeds completely — the target is fully convinced, deceived, or intimidated."
        ),
    }
)

_STEALTH_DESCRIPTIONS: types.MappingProxyType[ContestOutcome, str] = types.MappingProxyType(
    {
        ContestOutcome.TARGET_DOMINATES: ("The target spots the actor immediately and reacts decisively."),
        ContestOutcome.TARGET_RESISTS: ("The target notices something suspicious — the actor is partially detected."),
        ContestOutcome.ACTOR_SUCCEEDS: ("The actor moves unseen, though not perfectly — they pass unnoticed for now."),
        ContestOutcome.ACTOR_DOMINATES: ("The actor is completely invisible to the target — a flawless stealth."),
    }
)


def _get_descriptions(contest_type: ContestType) -> types.MappingProxyType[ContestOutcome, str]:
    if contest_type == ContestType.COMBAT:
        return _COMBAT_DESCRIPTIONS
    if contest_type == ContestType.STEALTH:
        return _STEALTH_DESCRIPTIONS
    return _SOCIAL_DESCRIPTIONS


@dataclass(frozen=True)
class ContestRoll:
    """Result of a contested dice roll."""

    contest_type: ContestType
    outcome: ContestOutcome
    actor_roll: int
    target_roll: int
    actor_bonus: int
    target_bonus: int

    @property
    def description(self) -> str:
        """Human-readable description of the outcome for prompt injection."""
        return _get_descriptions(self.contest_type)[self.outcome]


@dataclass(frozen=True)
class NPCAction:
    """Result of an NPC's autonomous turn — wraps an optional :class:`ContestRoll`.

    ``action_type`` stays a plain ``str`` (not a ``Literal``) because the
    upstream value comes from LLM JSON: the Actor schema declares the
    canonical vocabulary (ATTACK / TALK / MOVE / IDLE / STEALTH /
    PERSUADE / DECEIVE / INTIMIDATE) but a malformed response can yield
    anything. Validation happens at the ``cast.npc_turn`` boundary.
    """

    npc_uuid: UUID
    npc_name: str
    action_description: str
    action_type: str
    target: str | None
    contest_roll: ContestRoll | None


# ---------------------------------------------------------------------------
# Backward-compatible aliases so existing imports keep working during migration
# ---------------------------------------------------------------------------

CombatOutcome = ContestOutcome
"""Deprecated alias — use ContestOutcome instead."""

# Outcome aliases mapping old names → new names
CombatOutcome.NPC_OVERPOWERS = ContestOutcome.TARGET_DOMINATES  # type: ignore[attr-defined]
CombatOutcome.NPC_DEFENDS = ContestOutcome.TARGET_RESISTS  # type: ignore[attr-defined]
CombatOutcome.PLAYER_SUCCEEDS = ContestOutcome.ACTOR_SUCCEEDS  # type: ignore[attr-defined]
CombatOutcome.PLAYER_DOMINATES = ContestOutcome.ACTOR_DOMINATES  # type: ignore[attr-defined]


@dataclass(frozen=True)
class CombatRoll:
    """Backward-compatible wrapper around ContestRoll for combat.

    Deprecated — use ContestRoll directly.
    """

    outcome: ContestOutcome
    npc_roll: int
    player_roll: int
    npc_bonus: int

    @property
    def description(self) -> str:
        """Human-readable description of the outcome."""
        return _COMBAT_DESCRIPTIONS[self.outcome]


# ---------------------------------------------------------------------------
# Aggression
# ---------------------------------------------------------------------------


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
    rng = _rng or _active_rng()
    roll = rng.randint(1, _D20)
    return AggressionRoll(
        will_attack=roll >= threshold,
        roll=roll,
        threshold=threshold,
        mood=mood.lower(),
    )


# ---------------------------------------------------------------------------
# Contest roll
# ---------------------------------------------------------------------------


def _determine_contest_outcome(diff: int) -> ContestOutcome:
    """Map the target-vs-actor roll difference to a contest outcome.

    ``diff`` = target_total - actor_total.
    """
    if diff >= 5:
        return ContestOutcome.TARGET_DOMINATES
    if diff >= 0:
        return ContestOutcome.TARGET_RESISTS
    if diff >= -5:
        return ContestOutcome.ACTOR_SUCCEEDS
    return ContestOutcome.ACTOR_DOMINATES


def roll_contest(
    contest_type: ContestType,
    actor_skill: int,
    target_skill: int,
    _rng: random.Random | None = None,
) -> ContestRoll:
    """Roll 1d20 for each side, add skill bonuses, determine outcome.

    ``actor_skill`` and ``target_skill`` should be 0-10.
    For player-vs-NPC combat the player is the actor with skill 0.

    Outcome thresholds (target total vs actor total):
    - target total >= actor total + 5  → TARGET_DOMINATES
    - target total >= actor total      → TARGET_RESISTS
    - target total >= actor total - 5  → ACTOR_SUCCEEDS
    - target total <  actor total - 5  → ACTOR_DOMINATES
    """
    rng = _rng or _active_rng()
    actor_roll = rng.randint(1, _D20)
    target_roll = rng.randint(1, _D20)

    diff = (target_roll + target_skill) - (actor_roll + actor_skill)
    return ContestRoll(
        contest_type=contest_type,
        outcome=_determine_contest_outcome(diff),
        actor_roll=actor_roll,
        target_roll=target_roll,
        actor_bonus=actor_skill,
        target_bonus=target_skill,
    )


def roll_combat(npc_combat_skill: int, _rng: random.Random | None = None) -> CombatRoll:
    """Roll 1d20 for each side, add NPC combat_skill bonus, determine outcome.

    Deprecated — use ``roll_contest(ContestType.COMBAT, ...)`` instead.
    Kept for backward compatibility with existing call sites.
    """
    contest = roll_contest(ContestType.COMBAT, 0, npc_combat_skill, _rng=_rng)
    return CombatRoll(
        outcome=contest.outcome,
        npc_roll=contest.target_roll,
        player_roll=contest.actor_roll,
        npc_bonus=npc_combat_skill,
    )


# ---------------------------------------------------------------------------
# Serialization helpers — produce JSON-safe dicts for the turn_events log.
# Kept alongside the dataclasses so producers don't re-implement the mapping.
# ---------------------------------------------------------------------------


def contest_roll_to_dict(roll: ContestRoll) -> dict[str, Any]:
    """Serialize a :class:`ContestRoll` to a JSON-safe dict."""
    return {
        "contest_type": roll.contest_type.value,
        "outcome": roll.outcome.value,
        "actor_roll": roll.actor_roll,
        "target_roll": roll.target_roll,
        "actor_bonus": roll.actor_bonus,
        "target_bonus": roll.target_bonus,
        "description": roll.description,
    }


def combat_roll_to_dict(roll: CombatRoll) -> dict[str, Any]:
    """Serialize a (deprecated) :class:`CombatRoll` to a JSON-safe dict."""
    return {
        "outcome": roll.outcome.value,
        "player_roll": roll.player_roll,
        "npc_roll": roll.npc_roll,
        "npc_bonus": roll.npc_bonus,
        "description": roll.description,
    }


def aggression_roll_to_dict(roll: AggressionRoll) -> dict[str, Any]:
    """Serialize an :class:`AggressionRoll` to a JSON-safe dict."""
    return {
        "will_attack": roll.will_attack,
        "roll": roll.roll,
        "threshold": roll.threshold,
        "mood": roll.mood,
    }


def record_npc_contest_event(
    contest_roll: ContestRoll,
    npc: Any,
    action_type: str,
    target_name: str,
) -> None:
    """Emit a ``dice_contest`` turn event for an NPC-initiated contest."""
    record_turn_event(
        "dice_contest",
        {
            **contest_roll_to_dict(contest_roll),
            "actor_npc_name": npc.name,
            "action_type": action_type,
            "target_name": target_name,
        },
        npc_id=getattr(npc, "uuid", None),
    )
