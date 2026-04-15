"""NPC autonomous turn resolution.

After the player's turn, each active NPC in the scene gets a chance
to act.  Actions are LLM-driven via the NPC's Actor agent and returned
as structured ``NPCAction`` results.
"""

from __future__ import annotations

import asyncio
import json as _json
import types
from dataclasses import dataclass
from typing import Any

from loguru import logger

from cast.dice import CONTEST_SKILL_MAP, ContestRoll, ContestType, roll_contest
from cast.director_witness import WitnessedAggression, is_guard_occupation
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
_ACTION_TO_CONTEST: types.MappingProxyType[str, ContestType] = types.MappingProxyType(
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


@dataclass(frozen=True)
class NPCAction:
    """Result of an NPC's autonomous turn."""

    npc_uuid: str
    npc_name: str
    action_description: str
    action_type: str
    target: str | None
    contest_roll: ContestRoll | None


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
        return roll_contest(contest_type, actor_skill, 0)

    target_npc = _find_target_npc(target_name, game_state)
    if target_npc is None:
        logger.warning("NPC {} attempted {} against unknown target {!r}", npc.name, action_type, target_name)
        return None
    return roll_contest(contest_type, actor_skill, target_npc.get_attribute(skill_pair[1], 0))


def _apply_scene_mutation(
    npc_uuid: str,
    action_type: str,
    game_state: GameState,
) -> None:
    """Mutate the scene based on the NPC's action."""
    if action_type != "MOVE":
        return
    scene = game_state.current_scene
    if not scene:
        return
    scene.npcs_present = [snpc for snpc in scene.npcs_present if snpc.uuid != npc_uuid]


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


class NPCTurnResolver:
    """Resolves NPC autonomous actions during their turn in a round."""

    def __init__(self, game_state: GameState, actors: dict[str, Any]) -> None:
        self._gs = game_state
        self._actors = actors

    async def resolve_npc_turns(
        self,
        player_action_summary: str,
        witnessed_events: list[WitnessedAggression] | None = None,
    ) -> list[NPCAction]:
        """Resolve all NPC turns simultaneously. Called after player's action.

        ``witnessed_events`` threads the KER-18 proximity-witness
        broadcast from ``TurnOutputs`` into every per-NPC turn prompt.
        Guards in the same location as the vandalism receive an
        INCIDENT clause and react on the same turn the player smashes
        the shutter; other occupations get the vanilla prompt.
        """
        eligible = self._eligible_npcs()
        if not eligible:
            return []
        actions = await self._gather_actions(eligible, player_action_summary, witnessed_events or [])
        for action in actions:
            _apply_scene_mutation(action.npc_uuid, action.action_type, self._gs)
        return actions

    async def _gather_actions(
        self,
        eligible: list[tuple[str, Any, Any]],
        summary: str,
        witnessed_events: list[WitnessedAggression],
    ) -> list[NPCAction]:
        """Concurrently resolve actions for all eligible NPCs."""
        coros = self._build_resolve_coros(eligible, summary, witnessed_events)
        gathered = await asyncio.gather(*coros, return_exceptions=True)
        return _filter_successful(gathered, eligible)

    def _build_resolve_coros(
        self,
        eligible: list[tuple[str, Any, Any]],
        summary: str,
        witnessed_events: list[WitnessedAggression],
    ) -> list[Any]:
        """Build the list of per-NPC resolve coroutines.

        Extracted so :meth:`_gather_actions` keeps the ``asyncio.gather``
        call on one line without tripping WPS221 on the expanded
        comprehension that reads the witnessed-events kwarg.
        """
        return [self._resolve_single_npc(npc, actor, summary, witnessed_events) for _, npc, actor in eligible]

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
    ) -> NPCAction:
        """Ask one NPC's Actor what they do, parse response, roll if needed."""
        try:
            raw_response = await actor.execute(
                input_data=_build_turn_prompt(npc, player_action_summary, self._gs, witnessed_events),
                context={"npc": npc, "game_state": self._gs, "is_npc_turn": True},
            )
        except Exception:
            logger.exception("LLM call failed for NPC {}", npc.name)
            raise
        return _build_npc_action(npc, raw_response, self._gs)


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
) -> str:
    """Build the prompt for an NPC's autonomous turn.

    When the KER-18 proximity-witness broadcast has published an
    aggressive event pinned to this NPC's scene location *and* the NPC
    is a guard-occupation watcher, an INCIDENT clause is appended to
    the base prompt so the Actor LLM can decide to intervene, raise
    the alarm, confront the player, or flee — in character.
    """
    scene = game_state.current_scene
    scene_desc = scene.description if scene else "unknown location"

    base_prompt = (
        "It is {name}'s turn.\n"
        "Recent events: {summary}\n"
        "Scene: {scene}\n"
        "Your mood: {mood}, Status: {status}\n\n"
        "Respond as JSON:\n"
        '{{"action": "Brief description of what you do", '
        '"type": "ATTACK|TALK|MOVE|IDLE|STEALTH|PERSUADE|DECEIVE|INTIMIDATE", '
        '"target": "name of target, \'player\', or null if no target"}}\n\n'
        "Stay in character. Most turns are routine. "
        "Only take dramatic action when justified by mood and situation."
    ).format(
        name=npc.name,
        summary=player_action_summary,
        scene=scene_desc,
        mood=npc.current_mood,
        status=npc.physical_status,
    )

    incident = _pick_incident_for_npc(npc, game_state, witnessed_events)
    if incident is None:
        return base_prompt
    return "{0}\n\n{1}".format(base_prompt, _format_incident_clause(npc, incident))


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
