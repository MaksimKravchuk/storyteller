"""NPC autonomous turn resolution.

After the player's turn, each active NPC in the scene gets a chance
to act.  Actions are LLM-driven via the NPC's Actor agent and returned
as structured ``NPCAction`` results.
"""

import asyncio
import json as _json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from loguru import logger

from cast.dice import (
    CONTEST_SKILL_MAP,
    ContestRoll,
    ContestType,
    NPCAction,
    record_npc_contest_event,
    roll_contest,
)
from cast.director_witness import WitnessedAggression, is_guard_occupation
from cast.npc_goal_resolution import resolve_actions_aftermath, resolve_goal_target_name
from cast.npc_opportunity import TACTICAL_HOSTILE_CLAUSE, get_opportunity_clause
from cast.wait_detection import INCAPACITATING_STATES
from models.game_state import GameState

# NPC action types that trigger a contest when targeting another character.
_CONTESTABLE_ACTIONS: frozenset[str] = frozenset(
    (
        "ATTACK",
        "STEALTH",
        "DECEIVE",
        "INTIMIDATE",
        "PERSUADE",
    )
)

# Maps NPC action type → ContestType for dice rolls.
_ACTION_TO_CONTEST: MappingProxyType[str, ContestType] = MappingProxyType(
    {
        "ATTACK": ContestType.COMBAT,
        "STEALTH": ContestType.STEALTH,
        "DECEIVE": ContestType.DECEPTION,
        "INTIMIDATE": ContestType.INTIMIDATION,
        "PERSUADE": ContestType.PERSUASION,
    }
)

# Statuses that prevent an NPC from acting.
_NPC_SKIP_STATUSES: frozenset[str] = INCAPACITATING_STATES | frozenset(("dead",))

_MAX_RAW_PREVIEW = 200


def _parse_npc_response(raw: str) -> dict:
    """Parse the NPC turn JSON response from the Actor."""
    try:
        return _json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("NPC turn response was not valid JSON: {}", raw[:_MAX_RAW_PREVIEW])
        return {"action": raw, "type": "IDLE", "target": None}


def _build_npc_action(npc: Any, raw_response: str, game_state: GameState) -> NPCAction:
    """Parse raw Actor response and build an NPCAction with optional contest roll."""
    parsed = _parse_npc_response(raw_response)
    action_type = parsed.get("type", "IDLE").upper()
    target = parsed.get("target")
    return NPCAction(
        npc_uuid=npc.uuid,
        npc_name=npc.name,
        action_description=parsed.get("action", raw_response),
        action_type=action_type,
        target=target,
        contest_roll=_roll_npc_contest(npc, action_type, target, game_state),
    )


def _find_target_npc(target_name: str, game_state: GameState) -> Any | None:
    """Find an NPC in the game state by name (case-insensitive)."""
    lower = target_name.lower()
    for npc in game_state.npcs.values():
        if npc.name.lower() == lower:
            return npc
    return None


def _roll_npc_contest(
    npc: Any,
    action_type: str,
    target_name: str | None,
    game_state: GameState,
) -> ContestRoll | None:
    """Roll a contest if the NPC action is contestable and has a target."""
    if action_type not in _CONTESTABLE_ACTIONS or not target_name:
        return None

    contest_type = _ACTION_TO_CONTEST[action_type]
    skill_pair = CONTEST_SKILL_MAP[contest_type]
    actor_skill = npc.get_attribute(skill_pair[0], 0)

    if target_name.lower() == "player":
        contest_roll = roll_contest(contest_type, actor_skill, 0)
    else:
        target_npc = _find_target_npc(target_name, game_state)
        if target_npc is None:
            logger.warning("NPC {} attempted {} against unknown target {!r}", npc.name, action_type, target_name)
            return None
        contest_roll = roll_contest(contest_type, actor_skill, target_npc.get_attribute(skill_pair[1], 0))

    record_npc_contest_event(contest_roll, npc, action_type, target_name)
    return contest_roll


def _apply_scene_mutation(
    npc_uuid: str,
    action_type: str,
    action_target: str | None,
    game_state: GameState,
) -> None:
    """Mutate the scene and location when an NPC moves away."""
    if action_type != "MOVE":
        return
    scene = game_state.current_scene
    if not scene:
        return
    if _is_targeting_scene_npc(action_target, npc_uuid, scene, game_state):
        return
    scene.npcs_present = [snpc for snpc in scene.npcs_present if snpc.uuid != npc_uuid]
    # npc.location_id is not updated here — we know the NPC left but not their destination.
    location = game_state.locations.get(scene.location_id)
    if location is None:
        logger.warning(
            "NPC {} MOVEd away but location_id {!r} is not registered; "
            "scene.npcs_present updated but location.npcs_present was not",
            npc_uuid,
            scene.location_id,
        )
        return
    location.remove_npc(npc_uuid)


def _is_targeting_scene_npc(
    target: str | None,
    self_uuid: str,
    scene: Any,
    game_state: GameState,
) -> bool:
    """Return True when *target* names a co-located NPC (repositioning, not departure)."""
    if not target:
        return False
    lower_target = target.lower()
    if lower_target == "player":
        return True
    for snpc in scene.npcs_present:
        if snpc.uuid == self_uuid:
            continue
        peer = game_state.npcs.get(snpc.uuid)
        if peer and peer.name.lower() == lower_target:
            return True
    return False


def _filter_successful(
    gathered: list[NPCAction | BaseException],
    eligible: list[tuple[str, Any, Any]],
) -> list[NPCAction]:
    """Keep successful NPC actions and log failures."""
    actions: list[NPCAction] = []
    for idx, outcome in enumerate(gathered):
        if isinstance(outcome, BaseException):
            npc_uuid, npc, _ = eligible[idx]
            logger.error("NPC turn failed for {} ({}): {}", npc.name, npc_uuid, outcome)
        else:
            actions.append(outcome)
    return actions


_PerNPCResolver = Any


@dataclass(frozen=True)
class _TurnContext:
    """Shared per-turn inputs passed through every NPC resolution."""

    resolve_single: _PerNPCResolver
    summary: str
    witnessed_events: list[WitnessedAggression]


async def _resolve_tail(
    ctx: _TurnContext,
    remaining: list[tuple[str, Any, Any]],
    peer_actions: list[tuple[str, str]],
    ordered_actions: list[NPCAction],
) -> list[NPCAction]:
    """Resolve NPCs one-by-one, threading peer actions forward.

    Failures are logged and skipped — one NPC's LLM hiccup must not
    stall the rest of the round.
    """
    for _, npc, actor in remaining:
        action = await _resolve_one_or_log(ctx, npc, actor, peer_actions)
        if action is not None:
            peer_actions = peer_actions + [(action.npc_name, action.action_description)]
            ordered_actions = ordered_actions + [action]
    return ordered_actions


async def _resolve_one_or_log(
    ctx: _TurnContext,
    npc: Any,
    actor: Any,
    peer_actions: list[tuple[str, str]],
) -> NPCAction | None:
    """Invoke ``ctx.resolve_single`` for one NPC; log and swallow any exception."""
    try:
        return await ctx.resolve_single(npc, actor, ctx.summary, ctx.witnessed_events, peer_actions)
    except Exception as exc:
        logger.error("NPC turn failed for {} ({}): {}", npc.name, npc.uuid, exc)
        return None


def _build_resolve_coros(
    ctx: _TurnContext,
    eligible: list[tuple[str, Any, Any]],
) -> list[Any]:
    """Build the list of per-NPC resolve coroutines for the parallel path."""
    summary = ctx.summary
    witnessed = ctx.witnessed_events
    return [ctx.resolve_single(npc, actor, summary, witnessed) for _, npc, actor in eligible]


class NPCTurnResolver:
    """Resolves NPC autonomous actions during their turn in a round."""

    def __init__(
        self,
        game_state: GameState,
        actors: dict[str, Any],
    ) -> None:
        self._gs = game_state
        self._actors = actors

    async def apply_goal_aftermath(self, actions: list[NPCAction], memory_manager: Any) -> None:
        """Run the goal/contest aftermath pipeline once per resolved action.

        Applies dice outcomes to targets, persists combat events as
        knowledge nodes, advances each actor's :class:`~models.goal.Goal`,
        and flips matching world threads on goal completion.
        """
        await resolve_actions_aftermath(actions, self._gs, memory_manager)

    async def resolve_npc_turns(
        self,
        player_action_summary: str,
        witnessed_events: list[WitnessedAggression] | None = None,
        is_aggressive: bool = False,
    ) -> list[NPCAction]:
        """Resolve all NPC turns after the player's action.

        ``witnessed_events`` threads the KER-18 proximity-witness
        broadcast from ``TurnOutputs`` into every per-NPC turn prompt.
        Guards in the same location as the vandalism receive an
        INCIDENT clause and react on the same turn the player smashes
        the shutter; other occupations get the vanilla prompt.

        ``is_aggressive`` (KER-21) switches the resolution strategy.
        Routine turns (TALK / EXPLORE / WAIT) keep the concurrent
        ``asyncio.gather`` path so NPC reactions do not serialize the
        common case. Aggressive turns resolve NPCs sequentially and
        thread a running peer-action summary into each subsequent
        prompt so the second and third NPC to react see what their
        peers just did and pick an in-character reaction instead of
        converging on the same template.
        """
        eligible = self._eligible_npcs()
        if not eligible:
            return []
        actions = await self._gather_actions(
            eligible,
            player_action_summary,
            witnessed_events or [],
            is_aggressive,
        )
        for action in actions:
            _apply_scene_mutation(action.npc_uuid, action.action_type, action.target, self._gs)
        return actions

    async def _gather_actions(
        self,
        eligible: list[tuple[str, Any, Any]],
        summary: str,
        witnessed_events: list[WitnessedAggression],
        is_aggressive: bool,
    ) -> list[NPCAction]:
        """Dispatch to the parallel or sequential path based on ``is_aggressive``."""
        ctx = _TurnContext(
            resolve_single=self._resolve_single_npc,
            summary=summary,
            witnessed_events=witnessed_events,
        )
        if is_aggressive:
            return await _resolve_tail(ctx, eligible, [], [])
        coros = _build_resolve_coros(ctx, eligible)
        gathered = await asyncio.gather(*coros, return_exceptions=True)
        return _filter_successful(gathered, eligible)

    def _eligible_npcs(self) -> list[tuple[str, Any, Any]]:
        """Return (uuid, npc, actor) for NPCs that can act this turn."""
        scene = self._gs.current_scene
        if not scene:
            return []
        entries: list[tuple[str, Any, Any]] = []
        for snpc in scene.npcs_present:
            entry = self._try_npc(snpc)
            if entry is not None:
                entries.append(entry)
        return entries

    def _try_npc(self, snpc: Any) -> tuple[str, Any, Any] | None:
        """Return (uuid, npc, actor) if the scene-NPC can act, else None."""
        if not snpc.uuid or snpc.uuid not in self._gs.npcs:
            return None
        npc = self._gs.npcs[snpc.uuid]
        if (npc.physical_status or "").lower() in _NPC_SKIP_STATUSES:
            return None
        actor = self._actors.get(snpc.uuid)
        if actor is None:
            return None
        return (snpc.uuid, npc, actor)

    async def _resolve_single_npc(
        self,
        npc: Any,
        actor: Any,
        player_action_summary: str,
        witnessed_events: list[WitnessedAggression],
        peer_actions: list[tuple[str, str]] | None = None,
    ) -> NPCAction:
        """Ask one NPC's Actor what they do, parse response, roll if needed."""
        prompt = _build_turn_prompt(npc, player_action_summary, self._gs, witnessed_events, peer_actions)
        try:
            reply = await actor.execute(
                input_data=prompt,
                context={
                    "npc": npc,
                    "game_state": self._gs,
                    "is_npc_turn": True,
                    "goal_target_name": resolve_goal_target_name(npc, self._gs),
                },
            )
        except Exception:
            logger.exception("LLM call failed for NPC {}", npc.name)
            raise
        return _build_npc_action(npc, reply.text, self._gs)


def _pick_incident_for_npc(
    npc: Any,
    game_state: GameState,
    witnessed_events: list[WitnessedAggression] | None,
) -> WitnessedAggression | None:
    """Return the first witnessed event that applies to this NPC.

    Only NPCs whose occupation passes :func:`is_guard_occupation` see
    an incident — this matches the Linear issue scope of "guards and
    watchmen" and keeps tailors and beggars from parroting alarm
    responses. The event must also pin to the NPC's current scene
    location so a shutter smash in the Forum does not surface in a
    tavern prompt.
    """
    if not witnessed_events or not is_guard_occupation(npc.occupation):
        return None
    scene = game_state.current_scene
    if scene is None:
        return None
    for event in witnessed_events:
        if event.location_id == scene.location_id:
            return event
    return None


def _build_turn_prompt(
    npc: Any,
    player_action_summary: str,
    game_state: GameState,
    witnessed_events: list[WitnessedAggression] | None = None,
    peer_actions: list[tuple[str, str]] | None = None,
) -> str:
    """Build the prompt for an NPC's autonomous turn.

    When the KER-18 proximity-witness broadcast has published an
    aggressive event pinned to this NPC's scene location *and* the NPC
    is a guard-occupation watcher, an INCIDENT clause is appended to
    the base prompt so the Actor LLM can decide to intervene, raise
    the alarm, confront the player, or flee — in character.

    When ``peer_actions`` is non-empty (KER-21 sequential aggressive
    path), a "peer reactions" clause is inserted so each NPC sees what
    its peers already did this turn and is pushed away from echoing
    the same template reaction.

    When the opportunity gate detects a co-located target named in a
    hostile relationship or a violence-flavoured knowledge fact, a
    directive OPPORTUNITY clause naming the specific target is appended
    and the baseline "most turns are routine" nudge is dropped.
    """
    opportunity_clause = get_opportunity_clause(npc, game_state)
    base_prompt = _format_base_turn_prompt(
        npc=npc,
        player_action_summary=player_action_summary,
        game_state=game_state,
        include_routine_nudge=opportunity_clause is None,
    )

    clauses: list[str] = [base_prompt]
    if peer_actions:
        clauses.append(_format_peer_actions_clause(peer_actions))
    incident = _pick_incident_for_npc(npc, game_state, witnessed_events)
    if incident is not None:
        clauses.append(_format_incident_clause(npc, incident))
    if opportunity_clause is not None:
        clauses.append(opportunity_clause)
        clauses.append(TACTICAL_HOSTILE_CLAUSE)
    return "\n\n".join(clauses)


def _format_base_turn_prompt(
    npc: Any,
    player_action_summary: str,
    game_state: GameState,
    include_routine_nudge: bool,
) -> str:
    scene = game_state.current_scene
    scene_desc = scene.description if scene else "unknown location"
    tail = (
        "Stay in character. Most turns are routine. Only take dramatic action when justified by mood and situation."
        if include_routine_nudge
        else "Stay in character."
    )
    return (
        "It is {name}'s turn.\nRecent events: {summary}\nScene: {scene}\nYour mood: {mood}, Status: {status}\n\n{tail}"
    ).format(
        name=npc.name,
        summary=player_action_summary,
        scene=scene_desc,
        mood=npc.current_mood,
        status=npc.physical_status,
        tail=tail,
    )


def _format_peer_actions_clause(peer_actions: list[tuple[str, str]]) -> str:
    """Render the KER-21 peer-reactions clause for the next NPC to act.

    Lists what each earlier NPC already did this turn and explicitly
    warns against echoing them — the behaviour that produced the
    carpenter / cook / guardsman chorus in the original bug report.
    """
    lines = ["- {0}: {1}".format(name, desc) for name, desc in peer_actions]
    return (
        "Other NPCs in this scene have already reacted this turn:\n"
        "{0}\n"
        "Do something DIFFERENT that fits your character; "
        "do not echo them."
    ).format("\n".join(lines))


def _format_incident_clause(npc: Any, incident: WitnessedAggression) -> str:
    """Render the KER-18 guard-witness incident clause for a prompt."""
    return (
        "INCIDENT: You have just witnessed: {description}\n"
        "You are a {occupation} standing in this location. Decide in "
        "character whether to intervene, raise the alarm, confront the "
        "player, or flee. Act decisively — this is not a routine moment."
    ).format(
        description=incident.description,
        occupation=npc.occupation or "watcher",
    )
