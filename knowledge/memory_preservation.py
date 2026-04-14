"""Preserve a departing NPC's session memories as hearsay for the rest of the city.

When an NPC is evicted from a scene (end-of-shift, schedule-driven
departure, or any other soft removal run through :class:`cast.npc_ticker.NPCTicker`),
any in-session ``PERSONAL_EXPERIENCE`` memories they witnessed
become invisible to the rest of the world. The memory nodes
themselves DO stay in the graph — the ticker never deletes them —
but they have ``scope=LOCAL`` + ``location_id=<scene>`` which means
the :class:`knowledge.query.KnowledgeQueryEngine` only surfaces them
for NPCs currently at that scene's location. Once the witnessing
NPC leaves, nobody else can learn what happened.

This module walks a departing NPC's ``WITNESSED`` memories and
creates one ``HEARSAY`` :class:`knowledge.node.KnowledgeNode` per
non-witness NPC in the same city, mirroring the shape produced by
:func:`knowledge.rumor.propagate_rumors` via the shared
:func:`knowledge.hearsay.write_hearsay_node` primitive. The
original ``WITNESSED`` edge is left intact so the departing NPC
keeps their own memory if they later return.

Each propagated memory is tagged with
``_DEPARTURE_PROPAGATION_TAG`` on the original node, which makes
subsequent evictions of the same NPC (or the same memory) cheap
no-ops — the tag is the idempotency key. Non-session memories and
memories that already carry the tag are skipped.

Scope note: this module handles the :class:`cast.npc_ticker.NPCTicker`
soft-eviction path only. The parallel
:meth:`timeline.effect_applier.EffectApplier._remove_npc` hard
removal path (deaths, forced moves) does not yet preserve memories
and should be handled in a follow-up PR.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from knowledge.hearsay import HearsayDraft, write_hearsay_node
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeSource,
)
from knowledge.rumor_scope import non_witness_city_npcs

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState


_DEPARTURE_PROPAGATION_TAG = "propagated_on_departure"
# Defensive cap: a very chatty NPC with dozens of session memories would
# otherwise explode the graph (O(memories x recipients)) on a single
# eviction. We propagate the newest memories first since they are most
# likely to be player-relevant.
_MAX_MEMORIES_PER_DEPARTURE = 20


def preserve_departing_npc_memories(
    graph: KnowledgeGraph,
    game_state: GameState,
    npc_id: str,
    scene_location_id: str,
) -> list[str]:
    """Fan a departing NPC's session memories out as hearsay for same-city non-witnesses.

    Returns the list of newly-created ``HEARSAY`` node UUIDs so
    callers can log or assert over them. Idempotent: memories
    already tagged ``propagated_on_departure`` are skipped, so
    repeated evictions of the same NPC never re-propagate the same
    memory. When no recipients are reachable (isolated scene or
    unknown ``scene_location_id``) the eligible memories are still
    tagged so subsequent evictions do not re-scan them every turn.
    """
    memories = _eligible_memories(graph, npc_id)
    if not memories:
        return []
    recipients = non_witness_city_npcs(game_state, scene_location_id, [npc_id])
    if not recipients:
        for memory in memories:
            _mark_propagated(memory)
        return []
    return _fan_out_hearsay(graph, memories, npc_id, game_state.game_clock, recipients)


def _fan_out_hearsay(
    graph: KnowledgeGraph,
    memories: list[KnowledgeNode],
    told_by: str,
    game_time: float,
    recipients: list[tuple[str, str]],
) -> list[str]:
    """Write a hearsay node per (memory, recipient) pair and tag each memory."""
    created_ids: list[str] = []
    for memory in memories:
        created_ids.extend(_hearsay_for_one_memory(graph, memory, told_by, game_time, recipients))
        _mark_propagated(memory)
    return created_ids


def _hearsay_for_one_memory(
    graph: KnowledgeGraph,
    memory: KnowledgeNode,
    told_by: str,
    game_time: float,
    recipients: list[tuple[str, str]],
) -> list[str]:
    """Write one HEARSAY node per recipient for a single memory."""
    return [
        write_hearsay_node(
            graph,
            HearsayDraft(
                text=memory.text,
                told_by=told_by,
                game_time=game_time,
                recipient_id=recipient_id,
                recipient_location=recipient_location,
            ),
        )
        for recipient_id, recipient_location in recipients
    ]


def _eligible_memories(graph: KnowledgeGraph, npc_id: str) -> list[KnowledgeNode]:
    """Return the departing NPC's propagate-able session memories, newest first.

    Walks ``WITNESSED`` edges outbound from ``npc_id`` and keeps
    nodes that are session-canon personal experiences, have
    non-empty text, and have not yet been tagged for departure
    propagation. Results are sorted newest-first by ``timestamp``
    (``None`` treated as oldest) and capped at
    ``_MAX_MEMORIES_PER_DEPARTURE``.
    """
    candidates: list[KnowledgeNode] = []
    for target_id, edge_type in graph.get_edges_from(npc_id):
        if edge_type != EdgeType.WITNESSED:
            continue
        node = graph.get_node(target_id)
        if node is not None and _is_propagatable(node):
            candidates.append(node)
    candidates.sort(
        key=lambda memory: float("-inf") if memory.timestamp is None else memory.timestamp,
        reverse=True,
    )
    return candidates[:_MAX_MEMORIES_PER_DEPARTURE]


def _is_propagatable(node: KnowledgeNode) -> bool:
    """Return True if a memory should be propagated on departure."""
    if node.canon != CanonSource.SESSION:
        return False
    if node.source != KnowledgeSource.PERSONAL_EXPERIENCE:
        return False
    if not (node.text or "").strip():
        return False
    return _DEPARTURE_PROPAGATION_TAG not in node.tags


def _mark_propagated(node: KnowledgeNode) -> None:
    """Tag a memory so subsequent departures do not re-propagate it.

    Uses list replacement rather than :meth:`list.append` so that a
    future default-mutable-list regression in the pydantic model
    can't cause accidental aliasing across ``KnowledgeNode``
    instances.
    """
    if _DEPARTURE_PROPAGATION_TAG not in node.tags:
        node.tags = [*node.tags, _DEPARTURE_PROPAGATION_TAG]
