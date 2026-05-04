"""Preserve a departing NPC's session memories as hearsay for the rest of the city.

When an NPC is evicted from a scene (end-of-shift, schedule-driven
departure, or any other soft removal run through :class:`cast.npc_ticker.NPCTicker`),
any in-session ``PERSONAL_EXPERIENCE`` memories they witnessed
become invisible to the rest of the world. The memory nodes
themselves DO stay in the graph — the ticker never deletes them —
but they have ``scope=LOCAL`` + ``location_id=<scene>`` which means
the :class:`knowledge.query.KnowledgeQueryEngine` only surfaces them
for NPCs currently at that scene's location. Once the witnessing
NPC leaves, nobody else can learn what happened. The same loss-of-
visibility hits the hard-removal path
(:meth:`timeline.effect_applier.EffectApplier._remove_npc`) when an
NPC is killed or forcibly relocated, which is why both call sites
funnel through this single primitive.

This module walks a departing NPC's ``WITNESSED`` memories and
creates one ``HEARSAY`` :class:`knowledge.node.KnowledgeNode` per
non-witness NPC in the same city, mirroring the shape produced by
:func:`knowledge.rumor.propagate_rumors` via the shared
:func:`knowledge.hearsay.write_hearsay_node` primitive. The
original ``WITNESSED`` edge is left intact so the departing NPC
keeps their own memory if they later return.

Each propagated (witness, memory) pair is flagged with
``_DEPARTURE_PROPAGATION_TAG`` on the ``WITNESSED`` *edge* — not on
the node. Co-witness broadcasts share a single ``PERSONAL_EXPERIENCE``
node across many witnesses, so a per-node tag would let the first
departing co-witness silently mute every subsequent co-witness's own
departure. The per-edge tag preserves the per-witness propagation
semantics: the same memory fans out as hearsay each time a fresh
co-witness leaves the scene, attributed to that specific informant.
Non-session memories and edges that already carry the tag are
skipped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

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
    npc_id: UUID,
    scene_location_id: UUID,
) -> list[UUID]:
    """Fan a departing NPC's session memories out as hearsay for same-city non-witnesses.

    Returns the list of newly-created ``HEARSAY`` node UUIDs so
    callers can log or assert over them. Idempotent per witness:
    once the ``WITNESSED`` edge from ``npc_id`` is tagged
    ``propagated_on_departure``, repeated evictions of the same NPC
    never re-propagate the same memory. Co-witnesses share the
    canonical node but each carry their own edge, so each fresh
    departure still gets a chance to fan its own copy out as
    hearsay. When no recipients are reachable (isolated scene or
    unknown ``scene_location_id``) the eligible edges are still
    tagged so subsequent evictions do not re-scan them every turn.
    """
    memories = _eligible_memories(graph, npc_id)
    if not memories:
        return []
    recipients = non_witness_city_npcs(game_state, scene_location_id, [npc_id])
    if not recipients:
        for memory in memories:
            _mark_propagated(graph, npc_id, memory.uuid)
        return []
    return _fan_out_hearsay(graph, memories, npc_id, game_state.game_clock, recipients)


def _fan_out_hearsay(
    graph: KnowledgeGraph,
    memories: list[KnowledgeNode],
    told_by: UUID,
    game_time: float,
    recipients: list[tuple[UUID, UUID]],
) -> list[UUID]:
    """Write a hearsay node per (memory, recipient) pair and tag each witness edge."""
    created_ids: list[UUID] = []
    for memory in memories:
        created_ids.extend(_hearsay_for_one_memory(graph, memory, told_by, game_time, recipients))
        _mark_propagated(graph, told_by, memory.uuid)
    return created_ids


def _hearsay_for_one_memory(
    graph: KnowledgeGraph,
    memory: KnowledgeNode,
    told_by: UUID,
    game_time: float,
    recipients: list[tuple[UUID, UUID]],
) -> list[UUID]:
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


def _eligible_memories(graph: KnowledgeGraph, npc_id: UUID) -> list[KnowledgeNode]:
    """Return the departing NPC's propagate-able session memories, newest first.

    Walks ``WITNESSED`` edges outbound from ``npc_id`` and keeps
    nodes that are session-canon personal experiences with non-empty
    text whose edge has not yet been tagged for departure
    propagation. Results are sorted newest-first by ``timestamp``
    (``None`` treated as oldest) and capped at
    ``_MAX_MEMORIES_PER_DEPARTURE``.
    """
    candidates: list[KnowledgeNode] = []
    for target_id, edge_type in graph.get_edges_from(npc_id):
        if edge_type != EdgeType.WITNESSED:
            continue
        node = graph.get_node(target_id)
        if node is not None and _is_propagatable(graph, node, npc_id):
            candidates.append(node)
    candidates.sort(
        key=lambda memory: float("-inf") if memory.timestamp is None else memory.timestamp,
        reverse=True,
    )
    return candidates[:_MAX_MEMORIES_PER_DEPARTURE]


def _is_propagatable(graph: KnowledgeGraph, node: KnowledgeNode, witness_id: UUID) -> bool:
    """Return True if ``witness_id``'s witnessing of ``node`` should propagate on departure."""
    if node.canon != CanonSource.SESSION:
        return False
    if node.source != KnowledgeSource.PERSONAL_EXPERIENCE:
        return False
    if not (node.text or "").strip():
        return False
    return not graph.edge_has_flag(witness_id, node.uuid, _DEPARTURE_PROPAGATION_TAG)


def _mark_propagated(graph: KnowledgeGraph, witness_id: UUID, memory_id: UUID) -> None:
    """Tag the ``witness_id → memory_id`` edge so that witness's re-departure is a no-op.

    Per-edge tagging keeps the idempotency key local to one witness:
    co-witnesses sharing the canonical node still propagate
    independently when they later leave the scene.
    """
    graph.flag_edge(witness_id, memory_id, _DEPARTURE_PROPAGATION_TAG)
