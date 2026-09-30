"""Deterministic social-goal completion predicates for NPC aftermath."""

from __future__ import annotations

from uuid import UUID

from models.game_state import GameState
from models.goal import Goal, GoalKind, GoalStatus
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind

_BEFRIEND_INTENSITY_THRESHOLD = 2
_STATUS_DEAD = "dead"
_WARM_RELATIONSHIP_KINDS = frozenset((RelationshipKind.FRIEND, RelationshipKind.ALLY, RelationshipKind.KIN))


def _relationship_to(npc: NPCCard, target_uuid: UUID) -> Relationship | None:
    """Return ``npc``'s directed relationship to ``target_uuid``, if any."""
    target_key = str(target_uuid)
    for relationship in npc.relationships:
        if relationship.target_uuid == target_key:
            return relationship
    return None


def _is_befriend_satisfied(actor: NPCCard, target: NPCCard) -> bool:
    """Return whether ``actor`` is warm enough toward ``target`` to be friends."""
    relationship = _relationship_to(actor, target.uuid)
    if relationship is None or relationship.kind not in _WARM_RELATIONSHIP_KINDS:
        return False
    return relationship.intensity >= _BEFRIEND_INTENSITY_THRESHOLD


def _living_befriend_target(goal: Goal | None, game_state: GameState) -> NPCCard | None:
    """Return the living target of an active BEFRIEND ``goal``, if any."""
    if goal is None or goal.kind is not GoalKind.BEFRIEND:
        return None
    if goal.status is not GoalStatus.ACTIVE or goal.target_uuid is None:
        return None
    target = game_state.npcs.get(goal.target_uuid)
    if target is None or (target.physical_status or "").lower() == _STATUS_DEAD:
        return None
    return target


def maybe_complete_social_goal(actor: NPCCard, game_state: GameState) -> None:
    """Complete supported social goals whose deterministic predicate is met.

    BEFRIEND completes when the actor's directed relationship to the goal
    target is FRIEND, ALLY, or KIN with intensity at least +2. Each goal is
    checked against its own ``target_uuid`` rather than this turn's action
    target, and a dead target never completes the goal. Both goal tiers are
    inspected, matching KILL completion semantics.
    """
    for goal in (actor.tactical_goal, actor.life_goal):
        target = _living_befriend_target(goal, game_state)
        if goal is not None and target is not None and _is_befriend_satisfied(actor, target):
            goal.status = GoalStatus.COMPLETED
            goal.record_progress("relationship reached friend threshold with {0}".format(target.name))
