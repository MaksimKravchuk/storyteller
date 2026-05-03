"""Effect-driven witness memory writes for EffectApplier.

When an EventEffect mutates NPC state (inventory, status, location,
...), this module emits graph memories so that co-located NPCs can
later recall the event via ``KnowledgeQueryEngine.get_memories_held_by``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from knowledge.memory_slots import EMPTY_SLOTS, MemorySlots, slot_kwargs
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from timeline._uuid_coerce import coerce_uuid
from timeline.effect_memory_slots import slots_for_effect
from timeline.event import EventEffect

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState


@dataclass(frozen=True)
class EffectPreState:
    """Target NPC state captured before an effect runs.

    ``MOVE_NPC`` mutates ``location_id`` and ``REMOVE_NPC`` pops the NPC
    from game state; without this pre-capture, the memory emitter would
    have no way to resolve the original departure location or name when
    composing witness text after the handler finishes.
    """

    npc_id: UUID | None = None
    npc_name: str = ""
    location_id: UUID | None = None


@dataclass(frozen=True)
class WitnessWrite:
    """Parameters for a single effect-driven graph write."""

    text: str
    witness_ids: list[UUID]
    scope: KnowledgeScope
    location_id: UUID | None
    game_time: float
    slots: MemorySlots = EMPTY_SLOTS


def capture_pre_state(game_state: GameState, effect: EventEffect) -> EffectPreState:
    """Snapshot the target NPC before the handler mutates or removes it."""
    npc_id = coerce_uuid(effect.effect_data.get("npc_id") or effect.target_id)
    if npc_id is None:
        return EffectPreState()
    npc = game_state.npcs.get(npc_id)
    if npc is None:
        return EffectPreState()
    return EffectPreState(npc_id=npc_id, npc_name=npc.name, location_id=npc.location_id)


def co_located_witnesses(
    game_state: GameState,
    location_id: UUID | None,
    exclude_id: UUID | None,
) -> list[UUID]:
    """Return NPC UUIDs at ``location_id`` excluding ``exclude_id``."""
    if location_id is None:
        return []
    location = game_state.locations.get(location_id)
    if location is None:
        return []
    return [npc_id for npc_id in location.npcs_present if npc_id != exclude_id]


def _plan_text(effect: EventEffect, name: str) -> str | None:
    etype = effect.effect_type.upper()
    edata = effect.effect_data
    if etype in ("ADD_ITEM", "REMOVE_ITEM") and not edata.get("item"):
        return None
    stat = edata.get("status", "")
    if stat.strip().lower() == "dead":
        status_text = "{0} died".format(name)
    elif stat:
        status_text = "{0}'s condition changed to {1}".format(name, stat)
    else:
        status_text = None
    attr = edata.get("attribute")
    return {
        "ADD_ITEM": "{0} acquired {1}".format(name, edata.get("item")),
        "REMOVE_ITEM": "{0} lost {1}".format(name, edata.get("item")),
        "CHANGE_ATTRIBUTE": "{0}'s {1} changed".format(name, attr) if attr else None,
        "CHANGE_STATUS": status_text,
        "MOVE_NPC": "{0} departed for {1}".format(name, edata.get("to_location_id"))
        if edata.get("to_location_id")
        else "{0} departed".format(name),
        "REMOVE_NPC": "{0} is no longer here".format(name),
    }.get(etype)


def write_witness_memories(graph: KnowledgeGraph, write: WitnessWrite) -> None:
    """Persist a memory to the graph: wider rumor/fact node + one shared personal node.

    Co-witnesses share a single ``PERSONAL_EXPERIENCE`` node — one
    ``WITNESSED`` edge per witness rather than one node per witness —
    so a scene with N bystanders adds 1 node and N edges instead of N
    near-duplicate nodes. ``write.slots`` flow onto both the broadcast
    and the shared personal node so downstream dedup keeps working.
    """
    slot_fields = slot_kwargs(write.slots)
    if write.scope != KnowledgeScope.LOCAL:
        wider_source = KnowledgeSource.FACT if write.scope >= KnowledgeScope.COUNTRY else KnowledgeSource.RUMOR
        graph.add_node(
            KnowledgeNode(
                text=write.text,
                scope=write.scope,
                source=wider_source,
                canon=CanonSource.SESSION,
                location_id=write.location_id,
                timestamp=write.game_time,
                **slot_fields,
            ),
        )
    if not write.witness_ids:
        return
    personal_id = graph.add_node(
        KnowledgeNode(
            text=write.text,
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            canon=CanonSource.SESSION,
            location_id=write.location_id,
            timestamp=write.game_time,
            **slot_fields,
        ),
    )
    for witness_id in write.witness_ids:
        graph.add_edge(witness_id, personal_id, EdgeType.WITNESSED)


def emit_memory(
    game_state: GameState,
    graph: KnowledgeGraph,
    effect: EventEffect,
    pre: EffectPreState,
) -> None:
    """Emit witness memories for ``effect``, if any.

    Silent when the target NPC was missing (empty pre-state), when the
    effect type has no planner entry (``ADD_KNOWLEDGE``, ``SPAWN_NPC``,
    unknown), or when a LOCAL-scope effect finds no co-located
    witnesses. CITY-scope effects still emit the wider rumor even
    without witnesses.
    """
    if pre.npc_id is None:
        return
    text = _plan_text(effect, pre.npc_name)
    if text is None:
        return
    etype = effect.effect_type.upper()
    stat_lower = effect.effect_data.get("status", "").lower().strip()
    scope = KnowledgeScope.CITY if etype == "CHANGE_STATUS" and stat_lower == "dead" else KnowledgeScope.LOCAL
    witness_ids = co_located_witnesses(game_state, pre.location_id, pre.npc_id)
    if not witness_ids and scope == KnowledgeScope.LOCAL:
        return
    write_witness_memories(
        graph,
        WitnessWrite(
            text=text,
            witness_ids=witness_ids,
            scope=scope,
            location_id=pre.location_id,
            game_time=game_state.game_clock,
            slots=slots_for_effect(effect, pre.npc_name),
        ),
    )
