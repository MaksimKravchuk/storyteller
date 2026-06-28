"""Off-scene life-goal progression — the world breathes when the player isn't watching.

When the game clock advances by a meaningful amount (>= ``_MIN_HOURS``),
:class:`NPCBackgroundTicker` walks every NPC with an active
:class:`~models.goal.Goal` of scope ``LIFE`` who is **not** present in
the current scene. Tactical goals are intentionally skipped — they live
only a handful of turns and exist to drive in-scene reactions, so
ticking them between scenes would be both noisy and out of character
(a "DEFEND" goal makes no sense across an off-scene hour). For each
contest-eligible NPC:

- If their target is co-located with them at their off-scene location,
  one contest is rolled and the outcome is applied via the same
  :mod:`cast.npc_goal_resolution` pipeline that on-scene NPC turns use,
  so a Brutus left alone with Marcus can finish what he started.
- Otherwise the combat goal accrues a single progress note ("waited
  offscreen for N hours") so the next time the player wanders back
  through, the Actor sees that time has passed and pressure has built.

Non-combat life-goal kinds are intentionally inert here. They are not a
fallback branch of the contest map: unseen social/economic actions do
not yet have deterministic relationship, memory, inventory, or task
effects, so ticking them off-screen would only manufacture noisy
progress. Social liveness is handled by on-scene actions plus the
deterministic goal-resolution predicates that can inspect real state.

Bounded: at most one contest per goal-holder per advance, only when the
target is reachable. No LLM call when no contest fires — the cheap path
is just a string append on the goal's progress notes.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any
from uuid import UUID

from cast._npc_combat_memory import CombatEvent, persist_combat_memory
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

_GOAL_KIND_TO_CONTEST: MappingProxyType[GoalKind, ContestType] = MappingProxyType(
    {GoalKind.KILL: ContestType.COMBAT},
)

# Document the deliberate non-contest boundary so new GoalKinds do not look like
# accidental fall-throughs from ``_GOAL_KIND_TO_CONTEST``. These kinds may still
# complete elsewhere when deterministic state proves success (for example a warm
# relationship threshold), but this ticker does not invent off-scene progress for
# them until their effects are explicitly modeled.
_INTENTIONALLY_INERT_OFFSCENE_GOAL_KINDS = frozenset(
    (
        GoalKind.PURSUE,
        GoalKind.ACQUIRE,
        GoalKind.PROTECT,
        GoalKind.FLEE,
        GoalKind.BEFRIEND,
        GoalKind.COURT,
        GoalKind.GOSSIP,
        GoalKind.TRADE,
        GoalKind.HELP,
        GoalKind.WARN,
        GoalKind.ASK,
        GoalKind.AVOID,
    ),
)


def _scene_present_uuids(game_state: GameState) -> set[UUID]:
    scene = game_state.current_scene
    if scene is None:
        return set()
    return {snpc.uuid for snpc in scene.npcs_present if snpc.uuid is not None}


def _is_eligible(npc: NPCCard, present_uuids: set[UUID]) -> bool:
    if npc.uuid in present_uuids:
        return False
    if (npc.physical_status or "").lower() in _NPC_SKIP_STATUSES:
        return False
    goal = npc.life_goal
    if goal is None or goal.status is not GoalStatus.ACTIVE:
        return False
    if goal.kind in _INTENTIONALLY_INERT_OFFSCENE_GOAL_KINDS:
        return False
    return goal.kind in _GOAL_KIND_TO_CONTEST


def _co_located_target(npc: NPCCard, game_state: GameState) -> NPCCard | None:
    goal = npc.life_goal
    if goal is None or not goal.target_uuid:
        return None
    target = game_state.npcs.get(goal.target_uuid)
    if target is None or not target.location_id:
        return None
    if target.location_id != npc.location_id:
        return None
    return target


def _roll_offscreen_contest(actor: NPCCard, target: NPCCard, contest_type: ContestType) -> ContestRoll:
    actor_attr, target_attr = CONTEST_SKILL_MAP[contest_type]
    return roll_contest(
        contest_type=contest_type,
        actor_skill=int(actor.get_attribute(actor_attr, 1)),
        target_skill=int(target.get_attribute(target_attr, 1)),
    )


def _record_offscreen_progress(npc: NPCCard, hours_advanced: float, note_suffix: str) -> None:
    goal = npc.life_goal
    if goal is None:
        return
    goal.turns_pursued += 1
    goal.record_progress("offscreen wait ({0:.1f}h): {1}".format(hours_advanced, note_suffix))


class NPCBackgroundTicker:
    """Run goal-driven off-scene NPC actions when the game clock advances."""

    def __init__(self, game_state: GameState, memory_manager: Any) -> None:
        self._gs = game_state
        self._memory = memory_manager

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
        if not any(npc.life_goal for npc in self._gs.npcs.values()):
            return
        present = _scene_present_uuids(self._gs)
        eligible = [npc for npc in self._gs.npcs.values() if _is_eligible(npc, present)]
        await self._tick_remaining(eligible, hours_advanced)

    async def _tick_remaining(self, remaining: list[NPCCard], hours_advanced: float) -> None:
        if not remaining:
            return
        await self._tick_one(remaining[0], hours_advanced)
        await self._tick_remaining(remaining[1:], hours_advanced)

    async def _tick_one(self, actor: NPCCard, hours_advanced: float) -> None:
        target = _co_located_target(actor, self._gs)
        if target is None:
            _record_offscreen_progress(actor, hours_advanced, "no co-located target")
            return
        await self._resolve_offscreen_contest(actor, target, hours_advanced)

    async def _resolve_offscreen_contest(self, actor: NPCCard, target: NPCCard, hours_advanced: float) -> None:
        goal = actor.life_goal
        if goal is None:
            return
        contest_type = _GOAL_KIND_TO_CONTEST.get(goal.kind)
        if contest_type is None:
            return
        predicted = predict_contest_outcome(_roll_offscreen_contest(actor, target, contest_type))
        if predicted is not None and self._memory is not None:
            await persist_combat_memory(
                self._memory,
                CombatEvent(
                    actor=actor,
                    target=target,
                    new_value=predicted.new_value,
                    kind=predicted.kind,
                    location_id=actor.location_id,
                ),
                self._gs,
            )
        if predicted is not None:
            commit_outcome(target, predicted)
        _record_offscreen_progress(actor, hours_advanced, "contest vs {0}".format(target.name))
        maybe_complete_kill_goal(actor, target, self._gs)
