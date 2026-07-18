"""Deterministic social-goal completion predicates for NPC aftermath."""

from __future__ import annotations

from uuid import UUID

from models.goal import Goal, GoalKind, GoalStatus
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind

_BEFRIEND_INTENSITY_THRESHOLD = 2
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


def _matches_befriend_target(goal: Goal | None, target_uuid: UUID) -> bool:
    """Return whether ``goal`` is an active BEFRIEND goal for ``target_uuid``."""
    if goal is None or goal.kind is not GoalKind.BEFRIEND:
        return False
    if goal.status is not GoalStatus.ACTIVE:
        return False
    return goal.target_uuid == target_uuid


def maybe_complete_social_goal(actor: NPCCard, target: NPCCard) -> None:
    """Complete supported social goals whose deterministic predicate is met.

    BEFRIEND completes when the actor's directed relationship to the goal
    target is FRIEND, ALLY, or KIN with intensity at least +2. Both goal
    tiers are inspected, matching KILL completion semantics.
    """
    if not _is_befriend_satisfied(actor, target):
        return
    for goal in (actor.tactical_goal, actor.life_goal):
        if goal is not None and _matches_befriend_target(goal, target.uuid):
            goal.status = GoalStatus.COMPLETED
            goal.record_progress("relationship reached friend threshold with {0}".format(target.name))
