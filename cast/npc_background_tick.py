"""Off-scene life-goal progression — the world breathes when the player isn't watching.

When the game clock advances by a meaningful amount (>= ``_MIN_HOURS``),
:class:`NPCBackgroundTicker` walks every NPC with an active
:class:`~models.goal.Goal` of scope ``LIFE`` who is **not** present in
the current scene and whose goal kind has a registered off-scene
resolver. Tactical goals are intentionally skipped — they live only a
handful of turns and exist to drive in-scene reactions, so ticking them
between scenes would be both noisy and out of character (a "DEFEND" goal
makes no sense across an off-scene hour).

Goal kinds are routed through ``_RESOLVERS``, a ``GoalKind → resolver``
dispatch table:

- ``KILL`` keeps its original behaviour: if the target is co-located,
  one combat contest is rolled and the outcome is applied via the same
  pipeline on-scene NPC turns use, so a Brutus left alone with Marcus
  can finish what he started; otherwise the goal accrues a progress note.
- ``PURSUE`` / ``ACQUIRE`` / ``REST`` run deterministic, no-LLM steps in
  :mod:`cast._npc_offscreen_resolvers`, each stamping a one-line
  ``last_outcome`` the Actor prompt reads on re-entry.

Eligibility is keyed on "the goal kind has a resolver" rather than the
old KILL-only contest filter. Unmapped kinds, including social goals, are
intentionally inert off-scene until unseen social acts have deterministic
relationship and memory mutation semantics. Registered resolvers never
call an LLM, so making more NPCs eligible adds pure-Python work, not tokens.

Bounded: at most one resolver step per goal-holder per advance. The KILL
contest still fires only when the target is reachable, and the cheap
path is just a string append on the goal's progress notes.
"""

from __future__ import annotations

from types import MappingProxyType
from uuid import UUID

from cast._npc_combat_memory import CombatEvent, persist_combat_memory
from cast._npc_offscreen_resolvers import (
    Resolver,
    TickContext,
    co_located_target,
    record_offscreen_progress,
    resolve_acquire,
    resolve_pursue,
    resolve_rest,
)
from cast._npc_outcome import commit_outcome, predict_contest_outcome
from cast.dice import CONTEST_SKILL_MAP, ContestRoll, ContestType, roll_contest
from cast.npc_goal_resolution import maybe_complete_kill_goal
from cast.wait_detection import INCAPACITATING_STATES
from models.game_state import GameState
from models.goal import GoalKind, GoalStatus
from models.npc_card import NPCCard

_NPC_SKIP_STATUSES: frozenset[str] = INCAPACITATING_STATES | frozenset(("dead",))

# Skip ticks below 1h: short turns (TALK ~3 min, EXAMINE ~30s) are routine
# motion, not enough time for an off-scene NPC to commit to a goal step.
_MIN_HOURS = 1.0


def _scene_present_uuids(game_state: GameState) -> set[UUID]:
    scene = game_state.current_scene
    if scene is None:
        return set()
    return {snpc.uuid for snpc in scene.npcs_present if snpc.uuid is not None}


def _roll_offscreen_contest(actor: NPCCard, target: NPCCard, contest_type: ContestType) -> ContestRoll:
    actor_attr, target_attr = CONTEST_SKILL_MAP[contest_type]
    return roll_contest(
        contest_type=contest_type,
        actor_skill=int(actor.get_attribute(actor_attr, 1)),
        target_skill=int(target.get_attribute(target_attr, 1)),
    )


async def _resolve_offscreen_contest(ctx: TickContext, actor: NPCCard, target: NPCCard, hours_advanced: float) -> None:
    predicted = predict_contest_outcome(_roll_offscreen_contest(actor, target, ContestType.COMBAT))
    if predicted is not None and ctx.memory is not None:
        await persist_combat_memory(
            ctx.memory,
            CombatEvent(
                actor=actor,
                target=target,
                new_value=predicted.new_value,
                kind=predicted.kind,
                location_id=actor.location_id,
            ),
            ctx.game_state,
        )
    if predicted is not None:
        commit_outcome(actor, target, predicted, ctx.game_state.turn_count)
    record_offscreen_progress(actor, hours_advanced, "contest vs {0}".format(target.name))
    maybe_complete_kill_goal(actor, target, ctx.game_state)


async def resolve_kill(ctx: TickContext, actor: NPCCard, hours_advanced: float) -> None:
    """Original KILL path: contest a co-located target, else record a wait.

    Preserved byte-for-byte (no ``last_outcome`` write) so the combat
    vendetta benchmarks stay identical.
    """
    target = co_located_target(actor, ctx.game_state)
    if target is None:
        record_offscreen_progress(actor, hours_advanced, "no co-located target")
        return
    await _resolve_offscreen_contest(ctx, actor, target, hours_advanced)


_RESOLVERS: MappingProxyType[GoalKind, Resolver] = MappingProxyType(
    {
        GoalKind.KILL: resolve_kill,
        GoalKind.PURSUE: resolve_pursue,
        GoalKind.ACQUIRE: resolve_acquire,
        GoalKind.REST: resolve_rest,
    },
)


def _is_eligible(npc: NPCCard, present_uuids: set[UUID]) -> bool:
    if npc.uuid in present_uuids:
        return False
    if (npc.physical_status or "").lower() in _NPC_SKIP_STATUSES:
        return False
    goal = npc.life_goal
    if goal is None or goal.status is not GoalStatus.ACTIVE:
        return False
    return goal.kind in _RESOLVERS


class NPCBackgroundTicker:
    """Run goal-driven off-scene NPC actions when the game clock advances."""

    def __init__(self, game_state: GameState, memory_manager: object) -> None:
        self._ctx = TickContext(game_state=game_state, memory=memory_manager)

    async def tick(self, hours_advanced: float) -> None:
        """Run one off-scene tick across every eligible NPC.

        Fast-path: scenarios without any goal-bearing NPC (the common
        case) skip the eligibility walk entirely. Sequential await via
        async recursion prevents two off-scene actors targeting the
        same victim from racing on ``physical_status`` mutation across
        the await point.
        """
        if hours_advanced < _MIN_HOURS:
            return
        game_state = self._ctx.game_state
        if not any(npc.life_goal for npc in game_state.npcs.values()):
            return
        present = _scene_present_uuids(game_state)
        eligible = [npc for npc in game_state.npcs.values() if _is_eligible(npc, present)]
        await self._tick_remaining(eligible, hours_advanced)

    async def _tick_remaining(self, remaining: list[NPCCard], hours_advanced: float) -> None:
        if not remaining:
            return
        await self._tick_one(remaining[0], hours_advanced)
        await self._tick_remaining(remaining[1:], hours_advanced)

    async def _tick_one(self, actor: NPCCard, hours_advanced: float) -> None:
        # Re-check liveness: ``eligible`` is snapshotted before the loop, so
        # an earlier KILL resolver may have killed this actor mid-tick. A
        # corpse must not run its resolver (e.g. complete an ACQUIRE goal).
        if (actor.physical_status or "").lower() in _NPC_SKIP_STATUSES:
            return
        goal = actor.life_goal
        if goal is None:
            return
        resolver = _RESOLVERS.get(goal.kind)
        if resolver is None:
            return
        await resolver(self._ctx, actor, hours_advanced)
