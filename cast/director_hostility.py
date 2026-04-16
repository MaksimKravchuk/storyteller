"""Director-side bridge to the mechanical hostility system.

Isolates the hostility bump + threshold check from
:class:`cast.director_execution.PlanExecutor` so the plan-executor
module stays within its import budget, and folds both operations into
one pass over the target NPCs so we only resolve names → UUIDs once
per aggressive turn.
"""

from __future__ import annotations

from cast.director_dialogue_helpers import resolve_target_uuids
from cast.hostility import RETALIATION_THRESHOLD, SEVERITY_HIGH, bump_hostility
from models.game_state import GameState


def apply_aggressive_turn(
    game_state: GameState,
    target_names: list[str],
    player_action: str,
) -> set[str]:
    """Bump hostility on each targeted NPC and return the UUIDs now past the retaliation threshold.

    Single pass: resolves target names through :func:`resolve_target_uuids`
    (which handles both NPC names and scene-NPC roles), mutates
    ``hostility_level`` + ``recent_hostile_actions`` + ``current_mood``
    via :func:`bump_hostility`, and collects the UUIDs whose post-bump
    hostility qualifies them for a forced retaliation roll. Returns an
    empty set when no targets were supplied.
    """
    if not target_names:
        return set()
    force_uuids: set[str] = set()
    for uuid in resolve_target_uuids(target_names, game_state):
        npc = game_state.npcs.get(uuid)
        if npc is None:
            continue
        bump_hostility(
            npc,
            turn=game_state.turn_count,
            player_action=player_action,
            severity=SEVERITY_HIGH,
        )
        if npc.hostility_level >= RETALIATION_THRESHOLD:
            force_uuids.add(uuid)
    return force_uuids
