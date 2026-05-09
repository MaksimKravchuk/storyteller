"""Scene-swap consolidation hook.

Before :class:`models.scene.Scene` is replaced on
:class:`~models.game_state.GameState`, the outgoing scene's action log
is handed to :func:`knowledge.scene_consolidation.consolidate_scene`
so a per-NPC summary memory and any significant-event nodes land in
the long-term graph. Lives here (not in
:mod:`cast.director_execution`) so the executor module's import
count stays inside the WPS budget.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from knowledge import scene_consolidation
from knowledge.memory import MemoryManager
from models.game_state import GameState


async def consolidate_outgoing_scene(
    memory_manager: MemoryManager,
    game_state: GameState,
    outgoing_scene: Any,
) -> None:
    """Persist the outgoing scene's action log, if any, then return.

    No-op when there is no outgoing scene yet (first turn) or the log
    is empty. Caller is expected to clear
    ``game_state.scene_action_log`` immediately after this returns.
    """
    if outgoing_scene is None or not game_state.scene_action_log:
        return
    present_npc_uuids = _present_npc_uuids(outgoing_scene, game_state)
    if not present_npc_uuids:
        return
    request = scene_consolidation.SceneConsolidationRequest(
        entries=game_state.scene_action_log,
        present_npc_uuids=present_npc_uuids,
        game_time=game_state.game_clock,
        location_id=outgoing_scene.location_id,
        player_subject_id=game_state.player.uuid,
    )
    await scene_consolidation.consolidate_scene(memory_manager, request)


def _present_npc_uuids(scene: Any, game_state: GameState) -> list[UUID]:
    """Return UUIDs of fully-initialised NPCs currently in *scene*."""
    npcs = game_state.npcs
    return [snpc.uuid for snpc in scene.npcs_present if _is_initialised_npc(snpc, npcs)]


def _is_initialised_npc(snpc: Any, npcs: dict[UUID, Any]) -> bool:
    """Return True when *snpc* is a registered NPC fully present in the scene."""
    return snpc.uuid is not None and snpc.uuid in npcs
