"""Anachronism encounter persistence helpers for dialogue turns.

Lives outside :mod:`cast.director_dialogue` so that module stays
under the WPS214 method-count budget while the closure of the
familiarity loop (the spec-mandated tagged ``MemoryEvent`` write that
``get_memories_about_concept`` reads back next turn) is still
testable in isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from knowledge import salience as salience_presets
from knowledge.memory import MemoryEvent, MemoryManager
from knowledge.node import KnowledgeScope
from models.game_state import GameState

if TYPE_CHECKING:
    from cast.anachronism import TurnAnachronismContext

_ANACHRONISM_MEMORY_FALLBACK = "saw something strange they could not place"


def anachronism_memory_description(base: Any) -> str:
    """Render the memory text for an NPC's exposure to an anachronistic moment.

    Prefer the classifier's ``perceived_rewrite`` when present — it is
    already framed in the NPC's worldview. Fall back to a generic
    placeholder so a downstream :meth:`KnowledgeQueryEngine.get_memories_held_by`
    pass still has *something* to read instead of an empty string.
    """
    return base.perceived_rewrite or _ANACHRONISM_MEMORY_FALLBACK


async def record_anachronism_memory(
    game_state: GameState,
    memory_manager: MemoryManager,
    work_items: list[Any],
    anachronism_ctx: TurnAnachronismContext | None,
) -> None:
    """Persist a tagged memory event so each NPC's familiarity counter increments.

    Without this write, the next time the same NPC is shown the same
    gadget the encounter counter would still read zero and the
    strangeness modifier would not decay — the familiarity loop in
    :class:`cast.anachronism.TurnAnachronismContext` is load-bearing
    on having something to read back.

    Skips silently when (a) no anachronism classifier ran, (b) the
    verdict was period-appropriate, or (c) the verdict carried no
    unfamiliar concepts (nothing useful to tag the memory with).
    """
    if anachronism_ctx is None or not work_items:
        return
    base = anachronism_ctx.base_or_empty
    if base.strangeness_score == 0 or not base.unfamiliar_concepts:
        return
    scene = game_state.current_scene
    await memory_manager.create_memory_from_event(
        MemoryEvent(
            event_description=anachronism_memory_description(base),
            witness_ids=[wi[0].uuid for wi in work_items],
            scope=KnowledgeScope.LOCAL,
            location_id=scene.location_id if scene else None,
            game_time=game_state.game_clock,
            salience=salience_presets.ANACHRONISM_ENCOUNTER,
            tags=list(base.unfamiliar_concepts),
            subject_id=game_state.player.uuid,
        ),
    )
