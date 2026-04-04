"""Pure helper functions for dialogue routing."""

from __future__ import annotations

import random
from typing import Any

from cast.dice import CombatOutcome, CombatRoll, roll_combat
from models.game_state import GameState


def role_matched_uuids(targets_lower: set[str], game_state: GameState) -> set[str]:
    """Return UUIDs of scene NPCs whose role matches a target name."""
    scene = game_state.current_scene
    if not scene:
        return set()
    matched: set[str] = set()
    for snpc in scene.npcs_present:
        if snpc.uuid and snpc.role.lower() in targets_lower:
            matched.add(snpc.uuid)
    return matched


def name_matched_uuids(targets_lower: set[str], game_state: GameState) -> set[str]:
    """Return UUIDs of NPCs whose name matches a target."""
    matched: set[str] = set()
    for uid, npc in game_state.npcs.items():
        if npc.name.lower() in targets_lower:
            matched.add(uid)
    return matched


def deduplicate_by_name(uuids: set[str], game_state: GameState) -> list[str]:
    """De-duplicate NPC UUIDs so each name appears only once."""
    seen: set[str] = set()
    unique_uuids: list[str] = []
    for uid in uuids:
        npc = game_state.npcs.get(uid)
        if npc and npc.name.lower() not in seen:
            seen.add(npc.name.lower())
            unique_uuids.append(uid)
    return unique_uuids


def resolve_target_uuids(target_names: list[str], game_state: GameState) -> list[str]:
    """Resolve target names to a de-duplicated list of NPC UUIDs."""
    targets_lower = {target.lower() for target in target_names}
    matched = role_matched_uuids(targets_lower, game_state) | name_matched_uuids(targets_lower, game_state)
    return deduplicate_by_name(matched, game_state)


def build_combat_action(
    player_action: str,
    npc: Any,
    is_aggressive: bool,
    _rng: random.Random | None = None,
) -> tuple[str, CombatRoll | None]:
    """Build action text and optional combat roll for an NPC interaction."""
    if not is_aggressive:
        return player_action, None
    combat_roll = roll_combat(npc.get_attribute("combat_skill", 3), _rng=_rng)
    status_hint = ""
    if combat_roll.outcome in (CombatOutcome.PLAYER_SUCCEEDS, CombatOutcome.PLAYER_DOMINATES):
        status_hint = (
            "\nThe NPC is injured. Update their physical status to reflect the injury. "
            "Append [STATUS: <description>] at the end of your response."
        )
    action_text = (
        "{0}\n\n"
        "[DICE ROLL: player {1} vs "
        "NPC {2}+{3}]\n"
        "OUTCOME: {4}\n"
        "You MUST narrate this outcome. Do NOT override the dice result.{5}"
    ).format(
        player_action,
        combat_roll.player_roll,
        combat_roll.npc_roll,
        combat_roll.npc_bonus,
        combat_roll.description,
        status_hint,
    )
    return action_text, combat_roll
