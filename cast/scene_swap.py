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

from loguru import logger

from cast.player_context import format_player_appearance, is_default_appearance
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
        # Non-empty log but zero resolved NPCs: the caller wipes the
        # log next, so this is a real loss, not a quiet no-op.
        logger.warning(
            "Scene action log has {} entries but no present NPC resolved at swap "
            "(location={}); scene memory will be dropped",
            len(game_state.scene_action_log),
            outgoing_scene.location_id,
        )
        return
    request = scene_consolidation.SceneConsolidationRequest(
        entries=game_state.scene_action_log,
        present_npc_uuids=present_npc_uuids,
        game_time=game_state.game_clock,
        location_id=outgoing_scene.location_id,
        player_subject_id=game_state.player.uuid,
        player_appearance=_player_appearance_for_summary(game_state),
    )
    await scene_consolidation.consolidate_scene(memory_manager, request)


def _player_appearance_for_summary(game_state: GameState) -> str | None:
    """Return the player's visible appearance, or ``None`` when uninformative.

    The placeholder ``unremarkable`` adds no information the summariser
    couldn't infer from the bare transcript, so we return ``None`` and
    let the rendered log fall back to the bare ``Player: ...`` form.
    """
    appearance = format_player_appearance(game_state.player)
    if is_default_appearance(appearance):
        return None
    return appearance


def _present_npc_uuids(scene: Any, game_state: GameState) -> list[UUID]:
    """Return UUIDs of fully-initialised NPCs currently in *scene*.

    A *partial* drop (some present NPCs registered, some not) is the
    same actor-registry desync the rest of this PR hardens against. The
    survivors still consolidate, so it would otherwise be silent: warn
    with the dropped UUIDs. The all-dropped case is already covered by
    the zero-witness warning in :func:`consolidate_outgoing_scene`, so
    only warn here when at least one NPC survived.
    """
    npcs = game_state.npcs
    present: list[UUID] = []
    dropped: list[UUID | None] = []
    for snpc in scene.npcs_present:
        if _is_initialised_npc(snpc, npcs):
            present.append(snpc.uuid)
        else:
            dropped.append(snpc.uuid)
    if dropped and present:
        logger.warning(
            "Scene consolidation dropped {} unregistered NPC(s) {} at swap "
            "(location={}); their scene memory will be lost",
            len(dropped),
            dropped,
            scene.location_id,
        )
    return present


def _is_initialised_npc(snpc: Any, npcs: dict[UUID, Any]) -> bool:
    """Return True when *snpc* is a registered NPC fully present in the scene."""
    return snpc.uuid is not None and snpc.uuid in npcs
