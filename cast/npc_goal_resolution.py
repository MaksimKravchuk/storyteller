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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cast._npc_combat_memory import CombatEvent, persist_combat_memory
from cast._npc_outcome import commit_outcome, predict_contest_outcome, resolve_target_npc
from cast.dice import ContestRoll, NPCAction
from models.game_state import GameState
from models.goal import GoalKind, GoalStatus
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
    """Advance the actor's goal counter and record what was tried this turn."""
    goal = actor.current_goal
    if goal is None or goal.status is not GoalStatus.ACTIVE:
        return
    goal.turns_pursued += 1
    goal.last_attempted_action = action_type
    goal.record_progress("{0}: {1}".format(action_type, action_description))


def maybe_complete_kill_goal(actor: NPCCard, target: NPCCard, game_state: GameState) -> None:
    """Flip a KILL goal + matching open thread when ``target`` ends up dead."""
    goal = actor.current_goal
    if goal is None or goal.kind is not GoalKind.KILL:
        return
    if (target.physical_status or "").lower() != _STATUS_DEAD:
        return
    goal.status = GoalStatus.COMPLETED
    if not (actor.uuid and target.uuid):
        return
    for thread in game_state.world_state.threads:
        joined = actor.uuid in thread.involved_npcs and target.uuid in thread.involved_npcs
        if thread.status == _THREAD_OPEN and joined:
            thread.status = _THREAD_RESOLVED


async def _resolve_one_aftermath(
    aftermath: ActionAftermath,
    game_state: GameState,
    memory_manager: Any,
) -> None:
    """Predict outcome, persist memory, commit outcome, advance goal.

    Order matters and is now atomic: the dice are read in a pure
    prediction, the memory record is persisted *before* the target's
    state mutates, and only then does the commit + goal update run.
    A memory-write failure thus leaves the target untouched and the
    goal unadvanced — the player sees the engine error and the world
    stays consistent (no dead body without a memory of the kill).
    """
    target = resolve_target_npc(aftermath.target_name, game_state)
    predicted = predict_contest_outcome(aftermath.contest_roll)
    if predicted is not None and target is not None and memory_manager is not None:
        await persist_combat_memory(
            memory_manager,
            CombatEvent(
                actor=aftermath.actor,
                target=target,
                new_value=predicted.new_value,
                kind=predicted.kind,
            ),
            game_state,
        )
    if predicted is not None and target is not None:
        commit_outcome(target, predicted)
    update_goal_progress(aftermath.actor, aftermath.action_type, aftermath.action_description)
    if target is not None:
        maybe_complete_kill_goal(aftermath.actor, target, game_state)


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
    optional_aftermaths = [_build_aftermath(action, game_state) for action in actions]
    aftermaths = [aftermath for aftermath in optional_aftermaths if aftermath is not None]
    await _resolve_aftermath_chain(aftermaths, game_state, memory_manager)


def _build_aftermath(action: NPCAction, game_state: GameState) -> ActionAftermath | None:
    actor = game_state.npcs.get(action.npc_uuid)
    if actor is None:
        return None
    return ActionAftermath(
        actor=actor,
        action_type=action.action_type,
        action_description=action.action_description,
        target_name=action.target,
        contest_roll=action.contest_roll,
    )


async def _resolve_aftermath_chain(
    remaining: list[ActionAftermath],
    game_state: GameState,
    memory_manager: Any,
) -> None:
    """Async-recursion sequential await — see :func:`resolve_actions_aftermath`."""
    if not remaining:
        return
    await _resolve_one_aftermath(remaining[0], game_state, memory_manager)
    await _resolve_aftermath_chain(remaining[1:], game_state, memory_manager)
