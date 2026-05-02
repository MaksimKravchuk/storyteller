"""Deterministic tactical-goal generation, promotion, and expiry.

Three sources of tactical goals:

1. **Player aggression** — when the player attacks an NPC, the Director
   stamps a ``DEFEND`` goal on that NPC so the next-turn Actor pass
   sees a concrete short-term intent ("hit back at the player") in
   addition to whatever life-tier vendetta the NPC may already carry.

2. **Life-on-sight promotion** — when an NPC carrying an active
   life-tier ``KILL`` / ``PURSUE`` enters a scene that contains the
   target, the same ``kind`` is mirrored to the tactical slot so the
   on-turn aftermath ticks tactical progress (and a same-turn kill
   flips both tiers via :func:`cast.npc_goal_resolution.maybe_complete_kill_goal`).

3. **TTL expiry** — every turn-end the executor calls
   :func:`tick_tactical_ttl`, which abandons tactical goals whose
   ``created_on_turn`` is older than ``ttl`` turns or whose target has
   left the scene / died. Without this, a DEFEND from an attack the
   player ran away from would linger forever.

Pure functions, no LLM calls — restraint comes from the source gates,
not the generator. Living entirely in this module keeps
:mod:`cast.director_execution` from growing another responsibility.
"""

from __future__ import annotations

import types
from collections.abc import Iterable, Mapping
from uuid import UUID

from cast._npc_active_goal import select_active_goal
from models.game_state import GameState
from models.goal import Goal, GoalKind, GoalScope, GoalStatus
from models.npc_card import NPCCard

# How many turns a tactical goal is allowed to persist before expiry.
# Three is enough for "DEFEND while the player is still in scene
# trading blows" but short enough to retire stale intents the moment
# the situation moves on (player flees, scene changes).
TACTICAL_TTL = 3

# Tactical kinds that should mirror a life-tier KILL/PURSUE on sight.
# Mapping is one-to-one because the tactical kind shares the dice path
# of the life-tier kind it mirrors. ``MappingProxyType`` keeps the
# constant immutable, satisfying WPS407 without a private wrapper.
_LIFE_TO_TACTICAL_PROMOTION: Mapping[GoalKind, GoalKind] = types.MappingProxyType(
    {
        GoalKind.KILL: GoalKind.KILL,
        GoalKind.PURSUE: GoalKind.PURSUE,
    },
)


def assign_defend_goals_from_aggression(
    game_state: GameState,
    target_uuids: Iterable[UUID],
    player_action: str,
) -> None:
    """Stamp a tactical DEFEND on every NPC the player just attacked.

    Skips any NPC that already carries an ACTIVE tactical goal — the
    existing intent (e.g. a tactical KILL promoted from a life-tier
    vendetta) wins over a generic DEFEND so we don't downgrade
    Brutus-on-Marcus into a defensive twitch.
    """
    player_uuid = game_state.player.uuid
    current_turn = game_state.turn_count
    for uuid in target_uuids:
        npc = game_state.npcs.get(uuid)
        if npc is None:
            continue
        if npc.tactical_goal is not None and npc.tactical_goal.status is GoalStatus.ACTIVE:
            continue
        npc.tactical_goal = Goal(
            scope=GoalScope.TACTICAL,
            kind=GoalKind.DEFEND,
            description="React to the player's hostile action: {0}".format(player_action),
            target_uuid=player_uuid,
            created_on_turn=current_turn,
        )


def _build_tactical_promotion(npc: NPCCard, current_turn: int) -> Goal | None:
    """Return the tactical Goal to promote ``npc.life_goal`` into, or ``None``.

    ``None`` when the life goal is missing/closed, when the NPC
    already carries an ACTIVE tactical goal, or when the life kind is
    not in :data:`_LIFE_TO_TACTICAL_PROMOTION`. The four early returns
    keep the caller (``promote_life_goals_on_sight``) a tight scene
    walk.
    """
    life = npc.life_goal
    if life is None or life.status is not GoalStatus.ACTIVE:
        return None
    if npc.tactical_goal is not None and npc.tactical_goal.status is GoalStatus.ACTIVE:
        return None
    tactical_kind = _LIFE_TO_TACTICAL_PROMOTION.get(life.kind)
    if tactical_kind is None:
        return None
    return Goal(
        scope=GoalScope.TACTICAL,
        kind=tactical_kind,
        description="On-sight engagement of life-tier target: {0}".format(life.description),
        target_uuid=life.target_uuid,
        created_on_turn=current_turn,
    )


def _maybe_promote_at(uuid: UUID, game_state: GameState, present: set[UUID]) -> None:
    """Apply :func:`_build_tactical_promotion` to one NPC if their life-goal target shares the scene."""
    npc = game_state.npcs.get(uuid)
    if npc is None or npc.life_goal is None:
        return
    target_uuid = npc.life_goal.target_uuid
    if target_uuid is None or target_uuid not in present:
        return
    promotion = _build_tactical_promotion(npc, game_state.turn_count)
    if promotion is not None:
        npc.tactical_goal = promotion


def promote_life_goals_on_sight(game_state: GameState) -> None:
    """Auto-promote life KILL/PURSUE → tactical when target shares the scene.

    Called from :class:`PlanExecutor` after a scene is materialised so
    the on-turn Actor pass sees a tactical intent the same turn the
    avenger lays eyes on their mark.
    """
    scene = game_state.current_scene
    if scene is None:
        return
    present: set[UUID] = {snpc.uuid for snpc in scene.npcs_present if snpc.uuid is not None}
    if len(present) < 2:
        return
    for uuid in present:
        _maybe_promote_at(uuid, game_state, present)


_DEAD_STATUS = "dead"


def _expiry_reason(goal: Goal, game_state: GameState, current_turn: int, ttl: int) -> str | None:
    """Return a short reason if ``goal`` should expire, ``None`` to keep it alive.

    Two expiry conditions: TTL exceeded, or the target UUID resolves to
    a dead NPC. Target-out-of-scene is intentionally not a trigger —
    tactical goals should outlive a one-turn movement away so the NPC
    has a chance to chase.
    """
    if goal.created_on_turn is not None and current_turn - goal.created_on_turn >= ttl:
        return "tactical TTL expired ({0} turns)".format(ttl)
    if not goal.target_uuid:
        return None
    target = game_state.npcs.get(goal.target_uuid)
    if target is not None and (target.physical_status or "").lower() == _DEAD_STATUS:
        return "tactical target dead"
    return None


def tick_tactical_ttl(game_state: GameState, ttl: int = TACTICAL_TTL) -> None:
    """Expire tactical goals past TTL or whose target is dead.

    Called once per turn after :class:`NPCTicker.tick`. An expired goal
    flips to ABANDONED and a one-line reason lands in ``progress_notes``
    so a later Actor pass sees why the intent died.
    """
    current_turn = game_state.turn_count
    for npc in game_state.npcs.values():
        goal = npc.tactical_goal
        if goal is None or goal.status is not GoalStatus.ACTIVE:
            continue
        reason = _expiry_reason(goal, game_state, current_turn, ttl)
        if reason is None:
            continue
        goal.status = GoalStatus.ABANDONED
        goal.record_progress(reason)


def has_active_tactical_goal(npc: NPCCard) -> bool:
    """True iff ``npc`` is currently driven by a tactical goal.

    Used by :class:`NPCTicker` to skip schedule eviction on NPCs that
    are mid-reaction — a guard who just took a swing at the player is
    not going to wander off to the barracks because the in-game clock
    rolled past sundown.
    """
    active = select_active_goal(npc)
    return active is not None and active.scope is GoalScope.TACTICAL
