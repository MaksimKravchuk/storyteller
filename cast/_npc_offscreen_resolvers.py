"""Deterministic off-scene resolvers for non-KILL life goals.

The off-scene background ticker (:mod:`cast.npc_background_tick`) used to
process exactly one :class:`~models.goal.GoalKind` — ``KILL`` — because
that was the only kind wired to a contest. Every other motivation was
filtered out before it could make a single step, so a PURSUE/ACQUIRE/REST
goal sat inert whenever the player looked away.

This module adds the missing deterministic resolvers. None of them call
an LLM, roll dice, or touch the knowledge graph: each is a pure-Python
state step plus a one-line ``last_outcome`` the Actor prompt reads when
the NPC next shares a scene with the player. That keeps the off-scene
fan-out cost flat (O(eligible NPCs), no tokens) while letting the world
breathe beyond the murder plots.

* ``PURSUE`` — note whether the quarry was caught up with or is still
  being tracked.
* ``ACQUIRE`` — accrue progress and, after ``_ACQUIRE_TICKS_TO_SECURE``
  off-scene steps, secure the objective and complete the goal.
* ``REST`` — a recoverable physical status heals to ``healthy`` and the
  goal completes; an already-healthy rester just logs the lull.

The ``KILL`` contest path lives in :mod:`cast.npc_background_tick` and is
deliberately left untouched (byte-for-byte) — it never sets
``last_outcome``. The shared :func:`co_located_target` /
:func:`record_offscreen_progress` helpers live here so both modules reuse
them without a circular import.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from models.game_state import GameState
from models.goal import GoalStatus
from models.npc_card import NPCCard

# Physical statuses an off-scene REST step heals back to full health.
_RECOVERABLE_STATUSES: frozenset[str] = frozenset(
    ("wounded", "injured", "hurt", "exhausted", "tired"),
)

# Off-scene ACQUIRE steps needed before the objective is secured.
_ACQUIRE_TICKS_TO_SECURE = 3

_UNKNOWN_QUARRY = "their quarry"


@dataclass(frozen=True)
class TickContext:
    """Read-only handle to the live state + memory a resolver needs.

    Passed to every resolver so the dispatch table can hold plain
    module-level functions (no bound methods, no protected-attribute
    reach-back into the ticker).
    """

    game_state: GameState
    memory: Any


# A goal-kind resolver: one deterministic off-scene step for an eligible NPC.
Resolver = Callable[[TickContext, NPCCard, float], Awaitable[None]]


def _goal_target_npc(actor: NPCCard, game_state: GameState) -> NPCCard | None:
    """Resolve the life-goal's target NPC by UUID, or ``None``."""
    goal = actor.life_goal
    if goal is None or not goal.target_uuid:
        return None
    return game_state.npcs.get(goal.target_uuid)


def co_located_target(actor: NPCCard, game_state: GameState) -> NPCCard | None:
    """Return the goal target iff it shares the actor's off-scene location."""
    target = _goal_target_npc(actor, game_state)
    if target is None or not target.location_id:
        return None
    if target.location_id != actor.location_id:
        return None
    return target


def record_offscreen_progress(
    actor: NPCCard,
    hours_advanced: float,
    note_suffix: str,
    *,
    last_outcome: str | None = None,
) -> None:
    """Bump the goal's turn counter and append a bounded progress note.

    When ``last_outcome`` is provided it is stamped on the goal so the
    Actor prompt can surface it directly; the KILL path passes ``None``
    so its prompt body stays unchanged.
    """
    goal = actor.life_goal
    if goal is None:
        return
    goal.turns_pursued += 1
    if last_outcome is not None:
        goal.last_outcome = last_outcome
    goal.record_progress("offscreen wait ({0:.1f}h): {1}".format(hours_advanced, note_suffix))


async def resolve_pursue(ctx: TickContext, actor: NPCCard, hours_advanced: float) -> None:
    """Advance a PURSUE goal: caught up with the quarry, or still tracking."""
    game_state = ctx.game_state
    target = co_located_target(actor, game_state)
    if target is None:
        quarry = _goal_target_npc(actor, game_state)
        name = _UNKNOWN_QUARRY if quarry is None else quarry.name
        outcome = "still on {0}'s trail".format(name)
    else:
        outcome = "caught up with {0} off-screen".format(target.name)
    record_offscreen_progress(actor, hours_advanced, outcome, last_outcome=outcome)


async def resolve_acquire(ctx: TickContext, actor: NPCCard, hours_advanced: float) -> None:
    """Advance an ACQUIRE goal; secure + complete it after enough steps."""
    goal = actor.life_goal
    if goal is None:
        return
    securing = goal.turns_pursued + 1 >= _ACQUIRE_TICKS_TO_SECURE
    if securing:
        outcome = "secured {0}".format(goal.description)
        record_offscreen_progress(actor, hours_advanced, outcome, last_outcome=outcome)
        goal.status = GoalStatus.COMPLETED
        return
    outcome = "made headway toward {0}".format(goal.description)
    record_offscreen_progress(actor, hours_advanced, outcome, last_outcome=outcome)


async def resolve_rest(ctx: TickContext, actor: NPCCard, hours_advanced: float) -> None:
    """Advance a REST goal: heal a recoverable status, else log the lull."""
    goal = actor.life_goal
    if goal is None:
        return
    if (actor.physical_status or "").lower() in _RECOVERABLE_STATUSES:
        actor.physical_status = "healthy"
        outcome = "rested off-screen and recovered to full health"
        record_offscreen_progress(actor, hours_advanced, outcome, last_outcome=outcome)
        goal.status = GoalStatus.COMPLETED
        return
    outcome = "rested off-screen; already in good health"
    record_offscreen_progress(actor, hours_advanced, outcome, last_outcome=outcome)
