"""Post-action processing for autonomous NPC turns.

When an NPC's autonomous action lands a contest, three things must
happen so the world stays coherent:

1. The target's physical status (or mood, for non-combat outcomes) must
   reflect the dice. Without this, an autonomous Brutus-vs-Marcus
   ATTACK that wins decisively leaves Marcus untouched — narration
   describes a stab, the model says nothing happened.
2. The clash must persist as a knowledge-graph node so co-located NPCs
   carry it as personal memory and downstream queries find it.
3. The actor's :class:`~models.goal.Goal` must advance — turns_pursued
   bumps, last_attempted_action records the choice, and on a kill the
   matching :class:`~models.world_state.WorldThread` flips to resolved.
   When both tactical and life KILL goals target the same victim they
   both flip together so neither tier keeps ticking.

The sequential per-action chain lives in :mod:`cast._npc_aftermath_chain`
to keep this module's public surface small.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cast import _npc_social_goal
from cast._npc_active_goal import kill_goals_targeting, select_active_goal
from cast._npc_aftermath_chain import build_aftermath, resolve_aftermath_chain
from cast.dice import ContestRoll, NPCAction
from models.game_state import GameState
from models.goal import GoalStatus
from models.npc_card import NPCCard
from models.world_state import ThreadStatus

_STATUS_DEAD = "dead"
_THREAD_OPEN: ThreadStatus = "open"
_THREAD_RESOLVED: ThreadStatus = "resolved"


@dataclass(frozen=True)
class ActionAftermath:
    """Bundle of inputs for one NPC action's post-resolution pass."""

    actor: NPCCard
    action_type: str
    action_description: str
    target_name: str | None
    contest_roll: ContestRoll | None


def update_goal_progress(actor: NPCCard, action_type: str, action_description: str) -> None:
    """Advance the actor's active-tier goal counter and record this turn's choice.

    Operates on whichever tier :func:`select_active_goal` returns —
    tactical preferred over life — so a tactical DEFEND doesn't
    accidentally bump a long-running KILL's ``turns_pursued``.
    """
    goal = select_active_goal(actor)
    if goal is None:
        return
    goal.turns_pursued += 1
    goal.last_attempted_action = action_type
    goal.record_progress("{0}: {1}".format(action_type, action_description))


def maybe_complete_kill_goal(actor: NPCCard, target: NPCCard, game_state: GameState) -> None:
    """Flip every matching KILL goal + open thread when ``target`` ends up dead.

    Both tiers are inspected via :func:`kill_goals_targeting`: a
    co-targeting tactical and life KILL flip together so the off-scene
    ticker and the Actor prompt agree that the vendetta is over.
    """
    if (target.physical_status or "").lower() != _STATUS_DEAD:
        return
    matched = kill_goals_targeting(actor, target.uuid)
    if not matched:
        return
    for goal in matched:
        goal.status = GoalStatus.COMPLETED
    for thread in game_state.world_state.threads:
        joined = actor.uuid in thread.involved_npcs and target.uuid in thread.involved_npcs
        if thread.status == _THREAD_OPEN and joined:
            thread.status = _THREAD_RESOLVED


def maybe_complete_social_goal(actor: NPCCard, target: NPCCard) -> None:
    """Complete supported social goals whose deterministic predicate is met."""
    _npc_social_goal.maybe_complete_social_goal(actor, target)


def resolve_goal_target_name(npc: Any, game_state: GameState) -> str | None:
    """Resolve an NPC's active-goal target UUID to its display name.

    Returned name flows into the Actor's context so the prompt can
    address the target by name (the goal stores only a UUID). Tactical
    preferred over life via :func:`select_active_goal`, so the resolved
    name and the rendered goal block always reference the same tier.
    """
    goal = select_active_goal(npc)
    if goal is None or not goal.target_uuid:
        return None
    target_npc = game_state.npcs.get(goal.target_uuid)
    return target_npc.name if target_npc else None


async def resolve_actions_aftermath(
    actions: list[NPCAction],
    game_state: GameState,
    memory_manager: Any,
) -> None:
    """Run the aftermath pipeline once per action, sequentially.

    Sequential execution avoids a race where two NPCs targeting the
    same victim concurrently mutate that victim's ``physical_status``
    across an ``await`` point — the second resumed coroutine could
    stomp the first's lethal outcome with a non-lethal one.
    """
    optional_aftermaths = [build_aftermath(action, game_state) for action in actions]
    aftermaths = [aftermath for aftermath in optional_aftermaths if aftermath is not None]
    await resolve_aftermath_chain(aftermaths, game_state, memory_manager)
