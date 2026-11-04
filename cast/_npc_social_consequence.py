"""Relationship and follow-on goal write-back for social events between NPCs.

Shared by the scheduled ``SOCIAL_MEMORY`` effect path and by autonomous
contest outcomes, so an NPC wronged (or helped) away from the player
forms the same grudge (or debt) either way.
"""

from __future__ import annotations

from types import MappingProxyType

from cast._relationship_drift import shift_relationship
from models.goal import Goal, GoalKind, GoalScope, GoalStatus
from models.npc_card import NPCCard

EVENT_HARM = "harm"
EVENT_KINDNESS = "kindness"

_GOAL_CANDIDATES: MappingProxyType[str, tuple[str, ...]] = MappingProxyType(
    {
        EVENT_HARM: ("KILL", "PURSUE"),
        EVENT_KINDNESS: ("HELP", "PROTECT"),
    },
)
# Harm lands exactly on the ENEMY band (-2) that opens the npc_opportunity
# retaliation window; kindness mirrors it onto ALLY (+2).
_INTENSITY_DELTA_BY_KIND: MappingProxyType[str, int] = MappingProxyType(
    {
        EVENT_HARM: -2,
        EVENT_KINDNESS: 2,
    },
)
_GOAL_DESCRIPTION_BY_KIND: MappingProxyType[str, str] = MappingProxyType(
    {
        EVENT_HARM: "Retaliate against {0} for off-screen harm.",
        EVENT_KINDNESS: "Repay a debt to {0} after off-screen kindness.",
    },
)


def _spawn_follow_on_goal(actor: NPCCard, target: NPCCard, kind: str) -> None:
    goal_kind = None
    for candidate in _GOAL_CANDIDATES.get(kind, ()):
        candidate_goal_kind = getattr(GoalKind, candidate, None)
        if isinstance(candidate_goal_kind, GoalKind):
            goal_kind = candidate_goal_kind
            break
    if goal_kind is None:
        return
    current_goal = target.life_goal
    if current_goal is not None and current_goal.status is GoalStatus.ACTIVE:
        return
    target.life_goal = Goal(
        scope=GoalScope.LIFE,
        kind=goal_kind,
        description=_GOAL_DESCRIPTION_BY_KIND[kind].format(actor.name),
        target_uuid=actor.uuid,
    )


def apply_social_consequence(actor: NPCCard, target: NPCCard, kind: str, turn: int | None = None) -> None:
    """Shift ``target``'s relationship toward ``actor`` and seed a follow-on goal.

    Unknown kinds are ignored. A ``harm`` turns the target hostile and may
    seed a KILL grudge; a ``kindness`` warms it and may seed a HELP debt.
    An already-active life goal is never overwritten.
    """
    if kind not in _INTENSITY_DELTA_BY_KIND:
        return
    shift_relationship(target, actor.uuid, _INTENSITY_DELTA_BY_KIND[kind], turn=turn)
    _spawn_follow_on_goal(actor, target, kind)
