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
from uuid import UUID

from loguru import logger

from cast.dice import (
    CONTEST_SKILL_MAP,
    ContestRoll,
    ContestType,
    NPCAction,
    record_npc_contest_event,
    roll_contest,
    seed_task_dice,
)
from cast import (
    _npc_turn_gate,
    emotional_memory as _em,
    npc_goal_resolution as _ngr,
    npc_opportunity as _npo,
    player_context,
    scene_log,
)
from cast.director_witness import WitnessedAggression, is_guard_occupation
from cast.wait_detection import INCAPACITATING_STATES
from models import game_state as gs_mod, scene_action_log as scene_action_log_mod

GameState = gs_mod.GameState
PlayerUtterance = player_context.PlayerUtterance

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

# Tail of the scene action log shown to NPCs each turn. Bounded so a
# long scene does not blow up the prompt; full log stays in GameState
# for scene-end consolidation.
_MAX_SCENE_LOG_ENTRIES = 25
_MAX_SCENE_LOG_DESC_CHARS = 200


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

    # NPC turns roll concurrently under asyncio.gather; give this task its own
    # base-derived RNG (no-op outside benchmark mode) so the contest outcome is
    # independent of which gathered LLM call finishes first.
    seed_task_dice(str(npc.uuid))
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


def _record_action_in_scene_log(game_state: GameState, action: NPCAction) -> None:
    """Append the resolved NPC action to ``GameState.scene_action_log``."""
    npc = game_state.npcs.get(action.npc_uuid)
    if npc is None:
        # The NPC resolved an action but is no longer registered: an
        # actor-registry desync (de-registration / swap race). Logged
        # at ERROR to match knowledge.memory's precedent for the same
        # root cause — silently dropping it would erase that NPC's
        # action from scene-end consolidation with no forensic trail.
        logger.error(
            "Resolved NPC action dropped from scene log: {} ({}) not in game_state.npcs",
            action.npc_uuid,
            action.action_type,
        )
        return
    scene_log.append_npc_action(game_state, npc, action)


def _build_player_utterance(
    game_state: GameState,
    summary: str,
    action_type: str,
) -> PlayerUtterance:
    """Bundle the current turn's player action into a :class:`PlayerUtterance`."""
    return PlayerUtterance(
        appearance=player_context.format_player_appearance(game_state.player),
        action_type=action_type,
        text=summary,
    )


def _record_resolved_actions(game_state: GameState, actions: list[NPCAction]) -> None:
    """Apply scene mutations and append each NPC action to the scene log."""
    for action in actions:
        _apply_scene_mutation(action.npc_uuid, action.action_type, action.target, game_state)
        _record_action_in_scene_log(game_state, action)


def _apply_scene_mutation(
    npc_uuid: UUID,
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


def _peer_matches(snpc: Any, self_uuid: UUID, lower_target: str, game_state: GameState) -> bool:
    """Return True when ``snpc`` is a co-located NPC whose name matches ``lower_target``."""
    if snpc.uuid is None or snpc.uuid == self_uuid:
        return False
    peer = game_state.npcs.get(snpc.uuid)
    return bool(peer and peer.name.lower() == lower_target)


def _is_targeting_scene_npc(
    target: str | None,
    self_uuid: UUID,
    scene: Any,
    game_state: GameState,
) -> bool:
    """Return True when *target* names a co-located NPC (repositioning, not departure)."""
    if not target:
        return False
    lower_target = target.lower()
    if lower_target == "player":
        return True
    return any(_peer_matches(snpc, self_uuid, lower_target, game_state) for snpc in scene.npcs_present)


def _filter_successful(
    gathered: list[NPCAction | BaseException],
    eligible: list[tuple[str, Any, Any]],
) -> list[NPCAction]:
    """Keep successful NPC actions and log failures.

    ``CancelledError`` is re-raised rather than logged: it inherits from
    ``BaseException``, and swallowing it would turn cooperative
    cancellation of the gathered NPC turns into a routine error line.
    """
    actions: list[NPCAction] = []
    for idx, outcome in enumerate(gathered):
        if isinstance(outcome, asyncio.CancelledError):
            raise outcome
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
    player_utterance: PlayerUtterance
    witnessed_events: list[WitnessedAggression]


def _build_resolve_coros(
    ctx: _TurnContext,
    eligible: list[tuple[str, Any, Any]],
) -> list[Any]:
    """Build the list of per-NPC resolve coroutines for the parallel path."""
    utterance = ctx.player_utterance
    witnessed = ctx.witnessed_events
    return [ctx.resolve_single(npc, actor, utterance, witnessed) for _, npc, actor in eligible]


class NPCTurnResolver:
    """Resolves NPC autonomous actions during their turn in a round."""

    def __init__(
        self,
        game_state: GameState,
        actors: dict[UUID, Any],
    ) -> None:
        self._gs = game_state
        self._actors = actors

    async def apply_goal_aftermath(self, actions: list[NPCAction], memory_manager: Any) -> None:
        """Run the goal/contest aftermath pipeline once per resolved action.

        Applies dice outcomes to targets, persists combat events as
        knowledge nodes, advances each actor's :class:`~models.goal.Goal`,
        and flips matching world threads on goal completion.
        """
        await _ngr.resolve_actions_aftermath(actions, self._gs, memory_manager)

    async def resolve_npc_turns(
        self,
        player_action_summary: str,
        witnessed_events: list[WitnessedAggression] | None = None,
        is_aggressive: bool = False,
        player_action_type: str = "",
    ) -> list[NPCAction]:
        """Resolve all NPC turns after the player's action.

        ``witnessed_events`` threads the KER-18 proximity-witness
        broadcast from ``TurnOutputs`` into every per-NPC turn prompt.
        Guards in the same location as the vandalism receive an
        INCIDENT clause and react on the same turn the player smashes
        the shutter; other occupations get the vanilla prompt.

        Every eligible NPC resolves concurrently. ``is_aggressive`` only
        decides whether routine NPCs may sit the turn out: visible
        violence wakes everyone.
        """
        eligible = self._eligible_npcs()
        if not is_aggressive and scene_action_log_mod.this_turn_npc_replies(self._gs.scene_action_log):
            eligible = _drop_routine_npcs(eligible, self._gs, witnessed_events or [])
        if not eligible:
            return []
        utterance = _build_player_utterance(self._gs, player_action_summary, player_action_type)
        actions = await self._gather_actions(eligible, utterance, witnessed_events or [])
        _record_resolved_actions(self._gs, actions)
        return actions

    async def _gather_actions(
        self,
        eligible: list[tuple[str, Any, Any]],
        utterance: PlayerUtterance,
        witnessed_events: list[WitnessedAggression],
    ) -> list[NPCAction]:
        """Resolve every eligible NPC concurrently; one NPC's failure is logged, not fatal."""
        ctx = _TurnContext(
            resolve_single=self._resolve_single_npc,
            player_utterance=utterance,
            witnessed_events=witnessed_events,
        )
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
        if snpc.uuid is None or snpc.uuid not in self._gs.npcs:
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
        player_utterance: PlayerUtterance,
        witnessed_events: list[WitnessedAggression],
    ) -> NPCAction:
        """Ask one NPC's Actor what they do, parse response, roll if needed."""
        # Refresh the NPC's deterministic mood + relationship drift from its
        # charged memories before the autonomous-turn prompt reads
        # ``current_mood`` — mirrors the dialogue path so an NPC the player
        # never addresses still acts on a fresh grudge instead of a stale
        # mood. Derivation is pure and idempotent within a turn.
        _em.apply_emotional_state(
            npc,
            self._gs.knowledge_graph,
            self._gs.game_clock,
            turn=self._gs.turn_count,
        )
        prompt = _build_turn_prompt(npc, player_utterance, self._gs, witnessed_events)
        try:
            reply = await actor.execute(
                input_data=prompt,
                context={
                    "npc": npc,
                    "game_state": self._gs,
                    "is_npc_turn": True,
                    "goal_target_name": _ngr.resolve_goal_target_name(npc, self._gs),
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


def _drop_routine_npcs(
    eligible: list[tuple[str, Any, Any]],
    game_state: GameState,
    witnessed_events: list[WitnessedAggression],
) -> list[tuple[str, Any, Any]]:
    """Keep only NPCs with their own reason to act; the player addressed someone else.

    Every NPC still gets its emotional state derived (ADR-0012) so a
    skipped NPC's mood and relationships stay fresh for its next turn.
    """
    kept: list[tuple[str, Any, Any]] = []
    for entry in eligible:
        npc = entry[1]
        _em.apply_emotional_state(npc, game_state.knowledge_graph, game_state.game_clock, turn=game_state.turn_count)
        witnessed = _pick_incident_for_npc(npc, game_state, witnessed_events) is not None
        if witnessed or _npc_turn_gate.has_own_reason_to_act(npc, game_state):
            kept.append(entry)
    return kept


def _coerce_player_utterance(player_input: PlayerUtterance | str) -> PlayerUtterance:
    """Wrap a bare string in a placeholder :class:`PlayerUtterance`.

    Lets tests that only exercise the INCIDENT / OPPORTUNITY / peer
    clauses pass the raw player text without constructing the full
    schema. Production callers always pass a real PlayerUtterance.
    """
    if isinstance(player_input, PlayerUtterance):
        return player_input
    return PlayerUtterance(appearance="", action_type="", text=player_input)


def _build_turn_prompt(
    npc: Any,
    player_utterance: PlayerUtterance | str,
    game_state: GameState,
    witnessed_events: list[WitnessedAggression] | None = None,
) -> str:
    """Build the prompt for an NPC's autonomous turn.

    ``player_utterance`` carries the per-turn ``Recent events:`` cue
    (literary phrasing built from the player's appearance + action
    type + raw input). A bare string is accepted for tests that only
    exercise the OPPORTUNITY / INCIDENT paths and do
    not care about the player utterance's verb mapping; it is wrapped
    in a placeholder :class:`PlayerUtterance` with no appearance.

    Other clauses (KER-18 INCIDENT for guard-occupation NPCs,
    opportunity gate) layer in on top.
    """
    utterance = _coerce_player_utterance(player_utterance)
    opportunity = _npo.get_opportunity_clause(npc, game_state)
    base_prompt = _format_base_turn_prompt(
        npc=npc,
        player_utterance=utterance,
        game_state=game_state,
        include_routine_nudge=opportunity is None,
    )
    optional = _optional_turn_clauses(npc, game_state, witnessed_events, opportunity)
    return "\n\n".join([base_prompt, *optional])


def _optional_turn_clauses(
    npc: Any,
    game_state: GameState,
    witnessed_events: list[WitnessedAggression] | None,
    opportunity: _npo.OpportunityClause | None,
) -> list[str]:
    """Collect the optional clauses appended after the base turn prompt."""
    clauses: list[str] = []
    scene_history = _format_scene_log_clause(game_state.scene_action_log, game_state.player)
    if scene_history:
        clauses.append(scene_history)
    incident = _pick_incident_for_npc(npc, game_state, witnessed_events)
    if incident is not None:
        clauses.append(_format_incident_clause(npc, incident))
    if opportunity is not None:
        clauses.append(opportunity.text)
        if opportunity.is_hostile:
            clauses.append(_npo.TACTICAL_HOSTILE_CLAUSE)
    return clauses


def _format_base_turn_prompt(
    npc: Any,
    player_utterance: PlayerUtterance,
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
        summary=player_utterance.render(),
        scene=scene_desc,
        mood=npc.current_mood,
        status=npc.physical_status,
        tail=tail,
    )


def _format_scene_log_entry(entry: Any, player: Any) -> str:
    """Render one scene-log entry as a bullet for the NPC prompt."""
    body = scene_log.render_scene_log_entry_body(
        entry,
        player_context.format_player_appearance(player),
        max_desc_chars=_MAX_SCENE_LOG_DESC_CHARS,
    )
    return "- [t={clock:.1f}] {body}".format(clock=entry.game_clock, body=body)


def _format_scene_log_clause(scene_action_log: list[Any], player: Any) -> str | None:
    """Render the per-scene chronological log as a prompt clause.

    Returns ``None`` when the log is empty so the caller can omit the
    section. Caps the rendered tail at :data:`_MAX_SCENE_LOG_ENTRIES`
    so a long scene cannot inflate the prompt; the full log stays in
    :class:`GameState` for scene-end consolidation regardless.
    """
    if not scene_action_log:
        return None
    tail = scene_action_log[-_MAX_SCENE_LOG_ENTRIES:]
    lines = [_format_scene_log_entry(entry, player) for entry in tail]
    return "THIS SCENE SO FAR:\n{0}".format("\n".join(lines))


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
