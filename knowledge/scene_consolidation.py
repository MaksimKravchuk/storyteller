"""Scene-end consolidation of the per-scene action log.

Lives outside :mod:`knowledge.memory` so the latter does not exceed
the project's per-module method/member budget. The two phases below
read every input from the scene log and call back into MemoryManager;
no graph state is touched directly here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from knowledge import node as _node, salience as salience_presets
from knowledge.memory_slots import MemorySlots
from models.scene_action_log import SceneActionEntry

if TYPE_CHECKING:
    from knowledge.memory import MemoryManager


@dataclass(frozen=True)
class SceneConsolidationRequest:
    """Bundle of inputs for :func:`consolidate_scene`.

    Keeps the public function signature within the WPS argument-count
    budget while still carrying every field the two phases need.
    """

    entries: list[SceneActionEntry]
    present_npc_uuids: list[UUID]
    game_time: float
    location_id: UUID | None
    player_subject_id: UUID | None


async def consolidate_scene(manager: MemoryManager, request: SceneConsolidationRequest) -> None:
    """Persist the per-scene action log into long-term memory.

    Two phases run in order:

    1. **Per-NPC summary.** One ``PERSONAL_EXPERIENCE`` node per NPC
       present at scene end, produced by
       :meth:`MemoryManager.summarize_interactions_batch` over a
       rendered transcript. Routine-dialogue salience.
    2. **Significant events.** One LOCAL node per
       :class:`SceneActionEntry` flagged ``significant`` and NOT
       already persisted by combat / witness hooks
       (``metadata['already_persisted']``). Each shared node is
       witnessed by every present NPC. Phase 2 entries fan out via
       :func:`asyncio.gather` so a long log does not serialise.

    No-op when the log is empty or no NPC was present.
    """
    if not request.entries or not request.present_npc_uuids:
        return
    await _summary_phase(manager, request)
    await _significant_phase(manager, request)


async def _summary_phase(manager: MemoryManager, request: SceneConsolidationRequest) -> None:
    """Phase 1 — write one summary memory per present NPC."""
    from knowledge.memory import DialoguePair

    rendered = _render_log_for_summariser(request.entries)
    pairs: list[DialoguePair] = [(uuid, rendered) for uuid in request.present_npc_uuids]
    await manager.summarize_interactions_batch(
        pairs,
        game_time=request.game_time,
        location_id=request.location_id,
        salience=salience_presets.ROUTINE_DIALOGUE,
        subject_id=request.player_subject_id,
    )


async def _significant_phase(manager: MemoryManager, request: SceneConsolidationRequest) -> None:
    """Phase 2 — write one shared LOCAL node per significant entry."""
    from knowledge.memory import MemoryEvent

    significant = [
        entry for entry in request.entries if entry.significant and not entry.metadata.get("already_persisted")
    ]
    if not significant:
        return
    coros = [
        manager.create_memory_from_event(
            MemoryEvent(
                event_description=entry.description,
                witness_ids=request.present_npc_uuids,
                scope=_node.KnowledgeScope.LOCAL,
                location_id=request.location_id,
                game_time=entry.game_clock,
                salience=_salience_for_entry(entry),
                slots=_slots_for_entry(entry),
                subject_id=entry.actor_uuid,
            ),
        )
        for entry in significant
    ]
    await asyncio.gather(*coros)


def _render_log_for_summariser(entries: list[SceneActionEntry]) -> str:
    """Flatten the scene log into a transcript the summariser prompt can read."""
    lines = [
        "{speaker}: {desc}".format(
            speaker=entry.actor_name or entry.action_type or "Event",
            desc=entry.description,
        )
        for entry in entries
    ]
    return "\n".join(lines)


def _salience_for_entry(entry: SceneActionEntry) -> float:
    """Pick a salience preset for a significant scene-log entry."""
    if entry.action_type == "ATTACK":
        return salience_presets.COMBAT
    if entry.action_type == "INTIMIDATE":
        return salience_presets.RETALIATION
    return salience_presets.OBJECT_INTERACTION


def _slots_for_entry(entry: SceneActionEntry) -> MemorySlots:
    """Derive structured slots for a significant scene-log entry."""
    return MemorySlots(
        subject=entry.actor_name or None,
        object=entry.target_name,
        action=entry.action_type.lower() or None,
    )
