"""Helpers for picking an NPC's currently-active goal.

NPCs may carry up to two goals: a long-lived ``life_goal`` and a
short-lived ``tactical_goal``. Both the Actor prompt and the on-turn
aftermath want "the goal driving this action right now" — that is the
tactical goal when one is active, otherwise the life goal. Off-scene
background ticks bypass these helpers and read ``life_goal`` directly,
because tactical goals are intentionally too ephemeral for the
between-scene cadence.

Module is private — callers reach these helpers through
``cast.npc_goal_resolution``.
"""

from __future__ import annotations

from uuid import UUID

from models.goal import Goal, GoalKind, GoalStatus
from models.npc_card import NPCCard


def select_active_goal(npc: NPCCard) -> Goal | None:
    """Return the goal an NPC is currently pursuing, or ``None``.

    Tactical takes precedence over life when both are ACTIVE; either
    tier alone is returned if it is the only one ACTIVE. Returns
    ``None`` when neither tier has an ACTIVE goal.
    """
    for candidate in (npc.tactical_goal, npc.life_goal):
        if candidate is not None and candidate.status is GoalStatus.ACTIVE:
            return candidate
    return None


def _matches_kill_target(goal: Goal | None, target_uuid: UUID | None) -> bool:
    """True iff ``goal`` is an ACTIVE KILL goal targeting ``target_uuid``.

    A ``None`` ``target_uuid`` means "any target" — used by callers that
    only care that the actor wants to kill *somebody*, not who.
    """
    if goal is None or goal.kind is not GoalKind.KILL:
        return False
    if goal.status is not GoalStatus.ACTIVE:
        return False
    return target_uuid is None or goal.target_uuid == target_uuid


def kill_goals_targeting(actor: NPCCard, target_uuid: UUID | None) -> list[Goal]:
    """Return every ACTIVE KILL goal on actor whose target matches ``target_uuid``.

    A vengeful NPC may carry both a life-tier KILL and a tactical-tier
    KILL targeting the same victim (the tactical tier is auto-promoted
    from the life tier on sight). When the target dies, both must flip
    to COMPLETED so neither tier keeps ticking.
    """
    candidates: tuple[Goal | None, ...] = (actor.tactical_goal, actor.life_goal)
    return [goal for goal in candidates if goal is not None and _matches_kill_target(goal, target_uuid)]
