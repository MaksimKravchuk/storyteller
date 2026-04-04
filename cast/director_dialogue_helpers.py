"""Pure helper functions for dialogue routing."""

from __future__ import annotations

import random
from typing import Any

from cast.dice import (
    CONTEST_SKILL_MAP,
    CombatOutcome,
    CombatRoll,
    ContestOutcome,
    ContestRoll,
    ContestType,
    roll_combat,
    roll_contest,
)
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


def _format_contest_text(
    player_action: str,
    contest_roll: ContestRoll,
    status_hint: str = "",
) -> str:
    """Format action text with dice roll result for prompt injection."""
    return (
        "{0}\n\n"
        "[DICE ROLL: actor {1}+{2} vs "
        "target {3}+{4}]\n"
        "OUTCOME: {5}\n"
        "You MUST narrate this outcome. Do NOT override the dice result.{6}"
    ).format(
        player_action,
        contest_roll.actor_roll,
        contest_roll.actor_bonus,
        contest_roll.target_roll,
        contest_roll.target_bonus,
        contest_roll.description,
        status_hint,
    )


def _combat_status_hint(outcome: ContestOutcome) -> str:
    """Return a status-update hint when the target is injured in combat."""
    if outcome in (ContestOutcome.ACTOR_SUCCEEDS, ContestOutcome.ACTOR_DOMINATES):
        return (
            "\nThe NPC is injured. Update their physical status to reflect the injury. "
            "Append [STATUS: <description>] at the end of your response."
        )
    return ""


def build_contested_action(
    player_action: str,
    npc: Any,
    is_aggressive: bool = False,
    contest_info: dict | None = None,
    _rng: random.Random | None = None,
) -> tuple[str, ContestRoll | None]:
    """Build action text and optional contest roll for an NPC interaction.

    If *is_aggressive* is True, a combat contest is rolled (takes priority).
    If *contest_info* is provided (``{"type": "...", "target": "..."}``),
    a contest of the specified type is rolled.
    Otherwise, plain text is returned with no roll.
    """
    if is_aggressive:
        return _roll_and_format(player_action, npc, ContestType.COMBAT, default_skill=3, _rng=_rng)

    if contest_info:
        ctype = ContestType(contest_info.get("type", "combat"))
        return _roll_and_format(player_action, npc, ctype, default_skill=0, _rng=_rng)

    return player_action, None


def _roll_and_format(
    player_action: str,
    npc: Any,
    contest_type: ContestType,
    default_skill: int = 0,
    _rng: random.Random | None = None,
) -> tuple[str, ContestRoll]:
    """Roll a contest and format the action text with the result."""
    skill_attr = CONTEST_SKILL_MAP[contest_type]
    contest_roll = roll_contest(contest_type, 0, npc.get_attribute(skill_attr, default_skill), _rng=_rng)
    status_hint = _combat_status_hint(contest_roll.outcome) if contest_type == ContestType.COMBAT else ""
    return _format_contest_text(player_action, contest_roll, status_hint), contest_roll


def build_combat_action(
    player_action: str,
    npc: Any,
    is_aggressive: bool,
    _rng: random.Random | None = None,
) -> tuple[str, CombatRoll | None]:
    """Build action text and optional combat roll for an NPC interaction.

    Deprecated — use ``build_contested_action`` instead.
    Kept for backward compatibility.
    """
    if not is_aggressive:
        return player_action, None
    combat_roll = roll_combat(npc.get_attribute("combat_skill", 3), _rng=_rng)
    status_hint = ""
    if combat_roll.outcome in (CombatOutcome.ACTOR_SUCCEEDS, CombatOutcome.ACTOR_DOMINATES):
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
