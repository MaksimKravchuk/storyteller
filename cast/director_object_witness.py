"""Witness-memory broadcast for object-interaction turns.

Mirrors :mod:`cast.director_dialogue_witness` for the INTERACT path:
when a player kicks in a door or smashes a window, every initialised
scene NPC should walk away with a ``PERSONAL_EXPERIENCE`` memory of
the event.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from knowledge import salience as salience_presets
from knowledge.memory import MemoryEvent, record_player_learned_fact
from knowledge.node import KnowledgeScope

if TYPE_CHECKING:
    from knowledge.memory import MemoryManager
    from models.game_state import GameState


async def emit_witness_memories(
    memory_manager: MemoryManager,
    game_state: GameState,
    witness_ids: list[UUID],
    delta_text: str,
) -> None:
    """Broadcast a ``PERSONAL_EXPERIENCE`` memory to initialised scene NPCs.

    Short-circuits when there is nothing to remember (no witnesses or
    empty delta) so a silent "bumping into a wall" INTERACT does not
    spam the graph with ghost memory nodes.
    """
    if not witness_ids or not delta_text:
        return
    scene = game_state.current_scene
    memory_result = await memory_manager.create_memory_from_event(
        MemoryEvent(
            event_description=delta_text,
            witness_ids=witness_ids,
            scope=KnowledgeScope.LOCAL,
            location_id=scene.location_id if scene else None,
            game_time=game_state.game_clock,
            salience=salience_presets.OBJECT_INTERACTION,
        ),
    )
    record_player_learned_fact(game_state.player, memory_result.canonical_id)
