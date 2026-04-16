"""Director-side helpers that bridge the mechanical hostility system.

These helpers sit between :class:`cast.director_execution.PlanExecutor`
and :mod:`cast.hostility` so the plan-executor module stays within its
WPS201 import budget. The plan executor calls them by name; the
implementations live here alongside their ``resolve_target_uuids`` +
``bump_hostility`` dependencies.
"""

from __future__ import annotations

from cast.director_dialogue_helpers import resolve_target_uuids
from cast.hostility import RETALIATION_THRESHOLD, SEVERITY_HIGH, bump_hostility
from models.game_state import GameState


def bump_target_hostility(
    game_state: GameState,
    target_names: list[str],
    player_action: str,
) -> None:
    """Bump ``hostility_level`` on each NPC named in the target list.

    Resolves through both NPC names and scene-NPC roles, matching the
    resolver :class:`cast.director_dialogue.DialogueHandler` uses, so
    role-only targets like ``"guard"`` — which do not match ``npc.name``
    directly — still get their counter bumped.
    """
    if not target_names:
        return
    for uuid in set(resolve_target_uuids(target_names, game_state)):
        npc = game_state.npcs.get(uuid)
        if npc is None:
            continue
        bump_hostility(
            npc,
            turn=game_state.turn_count,
            player_action=player_action,
            severity=SEVERITY_HIGH,
        )


def force_retaliation_uuids(
    game_state: GameState,
    target_names: list[str],
) -> set[str]:
    """UUIDs of targeted NPCs whose hostility is at or above the retaliation threshold.

    The retaliation handler normally skips NPCs whose mood did not
    change during dialogue. That gate misses the case where the mood
    was already at ``threatened`` before the turn and the bump did not
    push it further — a repeat assault that should still provoke a
    counter-attack. Forcing the roll for these UUIDs makes aggressive
    beats land every time hostility is high enough.
    """
    if not target_names:
        return set()
    return {uuid for uuid in resolve_target_uuids(target_names, game_state) if _above_threshold(game_state, uuid)}


def _above_threshold(game_state: GameState, uuid: str) -> bool:
    """Return ``True`` when a known NPC has crossed the retaliation threshold."""
    npc = game_state.npcs.get(uuid)
    return npc is not None and npc.hostility_level >= RETALIATION_THRESHOLD
