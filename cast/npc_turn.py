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

    async def resolve_npc_turns(self, player_action_summary: str) -> list[NPCAction]:
        """Resolve all NPC turns simultaneously. Called after player's action."""
        eligible = self._eligible_npcs()
        if not eligible:
            return []
        actions = await self._gather_actions(eligible, player_action_summary)
        for action in actions:
            _apply_scene_mutation(action.npc_uuid, action.action_type, self._gs)
        return actions

    async def _gather_actions(
        self,
        eligible: list[tuple[str, Any, Any]],
        summary: str,
    ) -> list[NPCAction]:
        """Concurrently resolve actions for all eligible NPCs."""
        coros = [self._resolve_single_npc(npc, actor, summary) for _, npc, actor in eligible]
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

    async def _resolve_single_npc(self, npc: Any, actor: Any, player_action_summary: str) -> NPCAction:
        """Ask one NPC's Actor what they do, parse response, roll if needed."""
        try:
            raw_response = await actor.execute(
                input_data=_build_turn_prompt(npc, player_action_summary, self._gs),
                context={"npc": npc, "game_state": self._gs, "is_npc_turn": True},
            )
        except Exception:
            logger.exception("LLM call failed for NPC {}", npc.name)
            raise
        return _build_npc_action(npc, raw_response, self._gs)


def _build_turn_prompt(npc: Any, player_action_summary: str, game_state: GameState) -> str:
    """Build the prompt for an NPC's autonomous turn."""
    scene = game_state.current_scene
    scene_desc = scene.description if scene else "unknown location"

    return (
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
