"""Contest-outcome application for autonomous NPC turns.

When an NPC's autonomous action lands a contest, dice — not the LLM —
decide whether the target is hurt, killed, or unmoved. This module
predicts the new state from the dice in a pure function and commits
it as a separate step, so callers can persist a memory record *before*
mutating the target — a memory-write failure then leaves the target
unchanged instead of stranding a dead body in the world without the
matching knowledge-graph node.

Lives separately from :mod:`cast.npc_goal_resolution` so the orchestrator
imports stay narrow and each module fits the WPS module-member budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cast.dice import ContestOutcome, ContestRoll, ContestType
from models.game_state import GameState
from models.npc_card import NPCCard

_STATUS_DEAD = "dead"
_STATUS_WOUNDED = "wounded"
_MOOD_FRIGHTENED = "frightened"


class OutcomeKind(str, Enum):
    """Which target field the predicted outcome mutates."""

    PHYSICAL = "physical"
    MOOD = "mood"


@dataclass(frozen=True)
class PredictedOutcome:
    """Pure-function prediction of how a contest changes its target.

    ``kind`` distinguishes a physical_status change from a current_mood
    change — used by the memory writer to pick the right verb
    ("attacked" vs "intimidated") so persisted events read truthfully.
    """

    new_value: str
    kind: OutcomeKind


def resolve_target_npc(target_name: str | None, game_state: GameState) -> NPCCard | None:
    """Look up an NPC by display name (case-insensitive); return ``None`` on miss."""
    if not target_name:
        return None
    lower = target_name.lower()
    for npc in game_state.npcs.values():
        if npc.name.lower() == lower:
            return npc
    return None


def _combat_outcome(outcome: ContestOutcome) -> PredictedOutcome | None:
    if outcome is ContestOutcome.ACTOR_DOMINATES:
        return PredictedOutcome(_STATUS_DEAD, OutcomeKind.PHYSICAL)
    if outcome is ContestOutcome.ACTOR_SUCCEEDS:
        return PredictedOutcome(_STATUS_WOUNDED, OutcomeKind.PHYSICAL)
    return None


def _intimidation_outcome(outcome: ContestOutcome) -> PredictedOutcome | None:
    if outcome is ContestOutcome.ACTOR_DOMINATES:
        return PredictedOutcome(_MOOD_FRIGHTENED, OutcomeKind.MOOD)
    return None


def predict_contest_outcome(contest_roll: ContestRoll | None) -> PredictedOutcome | None:
    """Pure prediction: what new state would the dice produce, if any?

    Returns ``None`` when the dice don't dictate a state change (target
    resisted, no roll, contest type that doesn't mutate state).
    """
    if contest_roll is None:
        return None
    if contest_roll.contest_type is ContestType.COMBAT:
        return _combat_outcome(contest_roll.outcome)
    if contest_roll.contest_type is ContestType.INTIMIDATION:
        return _intimidation_outcome(contest_roll.outcome)
    return None


def commit_outcome(target: NPCCard, predicted: PredictedOutcome) -> None:
    """Apply a predicted outcome to the target NPC's mutable state."""
    if predicted.kind is OutcomeKind.PHYSICAL:
        target.physical_status = predicted.new_value
    elif predicted.kind is OutcomeKind.MOOD:
        target.current_mood = predicted.new_value
