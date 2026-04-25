"""Sequential-await aftermath dispatch for NPC autonomous actions.

Holds the private chain helpers extracted from
:mod:`cast.npc_goal_resolution`. The chain is sequential rather than
``asyncio.gather``-based so two NPCs targeting the same victim cannot
race on ``physical_status`` mutation across an ``await`` point.

The public entry point lives back in :mod:`cast.npc_goal_resolution`;
this module only carries the per-action plumbing.
"""

from __future__ import annotations

from typing import Any

from cast._npc_combat_memory import CombatEvent, persist_combat_memory
from cast._npc_outcome import commit_outcome, predict_contest_outcome, resolve_target_npc
from cast.dice import NPCAction
from models.game_state import GameState


def build_aftermath(action: NPCAction, game_state: GameState) -> Any:
    """Bundle one ``NPCAction`` into an :class:`ActionAftermath`, or ``None``.

    The :class:`ActionAftermath` type is imported lazily to avoid a
    circular import — :mod:`cast.npc_goal_resolution` imports this
    module, and that module owns the dataclass.
    """
    from cast.npc_goal_resolution import ActionAftermath

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


async def resolve_one_aftermath(
    aftermath: Any,
    game_state: GameState,
    memory_manager: Any,
) -> None:
    """Predict outcome, persist memory, commit outcome, advance goal.

    Order matters and is atomic: the dice are read in a pure prediction,
    the memory record is persisted *before* the target's state mutates,
    and only then does the commit + goal update run. A memory-write
    failure thus leaves the target untouched and the goal unadvanced —
    the player sees the engine error and the world stays consistent
    (no dead body without a memory of the kill).
    """
    from cast.npc_goal_resolution import maybe_complete_kill_goal, update_goal_progress

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


async def resolve_aftermath_chain(
    remaining: list,
    game_state: GameState,
    memory_manager: Any,
) -> None:
    """Async-recursion sequential await — see :func:`resolve_actions_aftermath`."""
    if not remaining:
        return
    await resolve_one_aftermath(remaining[0], game_state, memory_manager)
    await resolve_aftermath_chain(remaining[1:], game_state, memory_manager)
