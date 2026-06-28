"""Deterministic off-scene resolvers for non-KILL life goals.

The off-scene background ticker (:mod:`cast.npc_background_tick`) used to
process exactly one :class:`~models.goal.GoalKind` — ``KILL`` — because
that was the only kind wired to a contest. Every other motivation was
filtered out before it could make a single step, so a PURSUE/ACQUIRE/REST
goal sat inert whenever the player looked away.

This module adds the missing deterministic resolvers. None of them call
an LLM, roll dice, or touch the knowledge graph: each is a pure-Python
state step plus a structured :class:`~models.goal.OffSceneOutcome` the
Actor prompt renders (localized) when the NPC next shares a scene with
the player. That keeps the off-scene fan-out cost flat (O(eligible NPCs),
no tokens) while letting the world breathe beyond the murder plots.

* ``PURSUE`` — caught up with the quarry, still tracking, or (when the
  quarry was killed by someone else) abandon the now-pointless chase.
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
from models.goal import GoalStatus, OffSceneOutcome, OffSceneOutcomeKind
from models.npc_card import NPCCard

# Substrings that mark a physical status as recoverable by an off-scene
# REST step. Matched as stems so free-form statuses ("wounded left arm",
# "injured shoulder") that the Actor stores verbatim still heal.
_RECOVERABLE_STEMS: frozenset[str] = frozenset(
    ("wound", "injur", "hurt", "exhaust", "tired", "bleed", "sick"),
)

# Off-scene ACQUIRE steps needed before the objective is secured.
_ACQUIRE_TICKS_TO_SECURE = 3

_STATUS_DEAD = "dead"
_STATUS_HEALTHY = "healthy"


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
    outcome: OffSceneOutcome | None = None,
) -> None:
    """Bump the goal's turn counter and append a bounded progress note.

    ``note_suffix`` is the English audit line for ``progress_notes``
    (matching the existing note convention). ``outcome`` is the
    locale-agnostic structure the Actor prompt later renders; the KILL
    path passes ``None`` so its prompt body stays unchanged.
    """
    goal = actor.life_goal
    if goal is None:
        return
    goal.turns_pursued += 1
    if outcome is not None:
        goal.last_outcome = outcome
    goal.record_progress("offscreen wait ({0:.1f}h): {1}".format(hours_advanced, note_suffix))


async def resolve_pursue(ctx: TickContext, actor: NPCCard, hours_advanced: float) -> None:
    """Advance a PURSUE goal: caught up, still tracking, or quarry dead.

    The quarry is resolved once and reused for every branch — the
    co-location test compares its ``location_id`` directly rather than
    re-fetching it.
    """
    quarry = _goal_target_npc(actor, ctx.game_state)
    if quarry is None:
        outcome = OffSceneOutcome(kind=OffSceneOutcomeKind.PURSUE_TRACKING_UNKNOWN)
        record_offscreen_progress(actor, hours_advanced, "still tracking the quarry", outcome=outcome)
        return
    if (quarry.physical_status or "").lower() == _STATUS_DEAD:
        goal = actor.life_goal
        outcome = OffSceneOutcome(kind=OffSceneOutcomeKind.PURSUE_TARGET_DEAD, detail=quarry.name)
        note = "pursuit ended ({0} dead)".format(quarry.name)
        record_offscreen_progress(actor, hours_advanced, note, outcome=outcome)
        if goal is not None:
            goal.status = GoalStatus.ABANDONED
        return
    if quarry.location_id and quarry.location_id == actor.location_id:
        outcome = OffSceneOutcome(kind=OffSceneOutcomeKind.PURSUE_CAUGHT_UP, detail=quarry.name)
        record_offscreen_progress(actor, hours_advanced, "caught up with {0}".format(quarry.name), outcome=outcome)
        return
    outcome = OffSceneOutcome(kind=OffSceneOutcomeKind.PURSUE_TRACKING, detail=quarry.name)
    record_offscreen_progress(actor, hours_advanced, "still tracking {0}".format(quarry.name), outcome=outcome)


async def resolve_acquire(ctx: TickContext, actor: NPCCard, hours_advanced: float) -> None:
    """Advance an ACQUIRE goal; secure + complete it after enough steps."""
    goal = actor.life_goal
    if goal is None:
        return
    if goal.turns_pursued + 1 >= _ACQUIRE_TICKS_TO_SECURE:
        outcome = OffSceneOutcome(kind=OffSceneOutcomeKind.ACQUIRE_SECURED, detail=goal.description)
        record_offscreen_progress(actor, hours_advanced, "secured {0}".format(goal.description), outcome=outcome)
        goal.status = GoalStatus.COMPLETED
        return
    outcome = OffSceneOutcome(kind=OffSceneOutcomeKind.ACQUIRE_PROGRESS, detail=goal.description)
    note = "made headway toward {0}".format(goal.description)
    record_offscreen_progress(actor, hours_advanced, note, outcome=outcome)


async def resolve_rest(ctx: TickContext, actor: NPCCard, hours_advanced: float) -> None:
    """Advance a REST goal: heal a recoverable status, else log the lull."""
    goal = actor.life_goal
    if goal is None:
        return
    lowered = (actor.physical_status or "").lower()
    if any(stem in lowered for stem in _RECOVERABLE_STEMS):
        actor.physical_status = _STATUS_HEALTHY
        outcome = OffSceneOutcome(kind=OffSceneOutcomeKind.REST_RECOVERED)
        record_offscreen_progress(actor, hours_advanced, "rested and recovered", outcome=outcome)
        goal.status = GoalStatus.COMPLETED
        return
    outcome = OffSceneOutcome(kind=OffSceneOutcomeKind.REST_AT_EASE)
    record_offscreen_progress(actor, hours_advanced, "rested", outcome=outcome)
