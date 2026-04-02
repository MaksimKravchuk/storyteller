"""Dialogue routing helpers for Director."""

from __future__ import annotations

import asyncio
from typing import Any

from cast.dice import CombatRoll, roll_combat
from cast.director_context import get_location_name
from models.game_state import GameState

_KEY_GAME_STATE = "game_state"


# ---------------------------------------------------------------------------
# Module-level pure functions (do not count toward WPS214)
# ---------------------------------------------------------------------------


def _role_matched_uuids(targets_lower: set[str], game_state: GameState) -> set[str]:
    """Return UUIDs of scene NPCs whose role matches a target name."""
    scene = game_state.current_scene
    if not scene:
        return set()
    matched: set[str] = set()
    for snpc in scene.npcs_present:
        if snpc.uuid and snpc.role.lower() in targets_lower:
            matched.add(snpc.uuid)
    return matched


def _name_matched_uuids(targets_lower: set[str], game_state: GameState) -> set[str]:
    """Return UUIDs of NPCs whose name matches a target."""
    matched: set[str] = set()
    for uid, npc in game_state.npcs.items():
        if npc.name.lower() in targets_lower:
            matched.add(uid)
    return matched


def _deduplicate_by_name(uuids: set[str], game_state: GameState) -> list[str]:
    """De-duplicate NPC UUIDs so each name appears only once."""
    seen: set[str] = set()
    unique_uuids: list[str] = []
    for uid in uuids:
        npc = game_state.npcs.get(uid)
        if npc and npc.name.lower() not in seen:
            seen.add(npc.name.lower())
            unique_uuids.append(uid)
    return unique_uuids


def _resolve_target_uuids(target_names: list[str], game_state: GameState) -> list[str]:
    """Resolve target names to a de-duplicated list of NPC UUIDs."""
    targets_lower = {target.lower() for target in target_names}
    name_matched = _name_matched_uuids(targets_lower, game_state)
    candidate_uuids = _role_matched_uuids(targets_lower, game_state) | name_matched
    return _deduplicate_by_name(candidate_uuids, game_state)


def _build_combat_action(
    player_action: str,
    npc: Any,
    is_aggressive: bool,
) -> tuple[str, CombatRoll | None]:
    """Build action text and optional combat roll for an NPC interaction."""
    if not is_aggressive:
        return player_action, None
    combat_roll = roll_combat(npc.get_attribute("combat_skill", 3))
    action_text = (
        "{0}\n\n"
        "[DICE ROLL: player {1} vs "
        "NPC {2}+{3}]\n"
        "OUTCOME: {4}\n"
        "You MUST narrate this outcome. Do NOT override the dice result."
    ).format(
        player_action,
        combat_roll.player_roll,
        combat_roll.npc_roll,
        combat_roll.npc_bonus,
        combat_roll.description,
    )
    return action_text, combat_roll


def _snpc_matches(snpc: Any, targets_lower: set[str], game_state: GameState) -> bool:
    """Check whether a single SceneNPC matches any of the target names."""
    if not snpc.uuid or snpc.uuid not in game_state.npcs:
        return False
    npc = game_state.npcs[snpc.uuid]
    return snpc.role.lower() in targets_lower or npc.name.lower() in targets_lower


def _known_scene_identifiers(scene: Any, game_state: GameState) -> set[str]:
    """Return lowercase roles and names of NPCs already in the scene."""
    npcs = game_state.npcs
    known = {snpc.role.lower() for snpc in scene.npcs_present}
    for snpc in scene.npcs_present:
        if snpc.uuid and snpc.uuid in npcs:
            known.add(npcs[snpc.uuid].name.lower())
    return known


async def _execute_npc_dialogue(
    npc: Any,
    actor: Any,
    action_text: str,
    combat_roll: CombatRoll | None,
    game_state: GameState,
) -> dict[str, str]:
    """Execute a single NPC dialogue and return the result entry."""
    response = await actor.execute(
        input_data=action_text,
        context={
            "npc": npc,
            _KEY_GAME_STATE: game_state,
            "location_name": get_location_name(npc.location_id, game_state),
        },
    )
    result_entry: dict[str, str] = {
        "npc_name": npc.name,
        "response": response,
    }
    if combat_roll:
        player = combat_roll.player_roll
        npc_total = "{0}+{1}".format(combat_roll.npc_roll, combat_roll.npc_bonus)
        outcome = combat_roll.outcome.value
        result_entry["combat_roll"] = "d20: player {0} vs NPC {1} → {2}".format(
            player,
            npc_total,
            outcome,
        )
    return result_entry


# ---------------------------------------------------------------------------
# DialogueHandler class (≤7 methods including __init__)
# ---------------------------------------------------------------------------


class DialogueHandler:
    """Routes dialogue to Actor agents and manages scene NPCs."""

    def __init__(self, game_state: GameState, actors: dict[str, Any]) -> None:
        self._gs = game_state
        self._actors = actors

    async def handle_dialogue(
        self,
        player_action: str,
        target_names: list[str],
        is_aggressive: bool = False,
    ) -> list[dict[str, str]]:
        """Route dialogue to the correct Actor agents."""
        work_items = self._collect_targets(target_names, player_action, is_aggressive)
        coros = [_execute_npc_dialogue(*wi, self._gs) for wi in work_items]
        return list(await asyncio.gather(*coros))

    def targets_match_scene_npcs(self, target_names: list[str]) -> bool:
        """Return True if any target name matches an initialised SceneNPC."""
        scene = self._gs.current_scene
        if not scene or not target_names:
            return False
        targets_lower = {target.lower() for target in target_names}
        return any(_snpc_matches(snpc, targets_lower, self._gs) for snpc in scene.npcs_present)

    def ensure_targets_in_scene(self, target_names: list[str]) -> None:
        """Make sure every target is represented as a SceneNPC."""
        from models.scene import SceneNPC

        scene = self._gs.current_scene
        if not scene:
            return
        known = _known_scene_identifiers(scene, self._gs)
        for target in target_names:
            if target.lower() not in known:
                scene.npcs_present.append(SceneNPC(role=target))

    async def init_scene_npcs(self, npc_generator: Any, register_fn: Any) -> list[Any]:
        """Initialise any SceneNPC objects that need full NPCCard + Actor."""
        scene = self._gs.current_scene
        if not scene:
            return []
        uninit = [snpc for snpc in scene.npcs_present if snpc.need_init]
        if not uninit:
            return []
        new_cards = await npc_generator.execute(
            input_data=[snpc.role for snpc in uninit],
            context={_KEY_GAME_STATE: self._gs},
        )
        for scene_npc, card in zip(uninit, new_cards):
            register_fn(card)
            scene_npc.uuid = card.uuid
        return list(new_cards)

    def _collect_targets(
        self,
        target_names: list[str],
        player_action: str,
        is_aggressive: bool,
    ) -> list[tuple[Any, Any, str, CombatRoll | None]]:
        """Match target names to NPCs and prepare dialogue work items."""
        matched_uuids = _resolve_target_uuids(target_names, self._gs)
        return [
            (
                self._gs.npcs[uid],
                self._actors[uid],
                *_build_combat_action(player_action, self._gs.npcs[uid], is_aggressive),
            )
            for uid in matched_uuids
            if uid in self._actors
        ]
