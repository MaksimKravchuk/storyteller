"""Shared helper for writing LOCAL HEARSAY nodes to the knowledge graph.

Both rumour propagation (:mod:`knowledge.rumor`) and departure-memory
preservation (:mod:`knowledge.memory_preservation`) write the same
node shape: a ``LOCAL``-scoped ``HEARSAY`` node anchored at the
recipient NPC's current location, with a ``TOLD_BY`` edge pointing
back to the originating witness. This helper centralises that write
so there is a single audit point for the node's shape + edge
metadata — the query engine's ``[Heard from someone] `` prefix is
keyed off ``source == HEARSAY``, so the two callers must stay in
lock-step.

Callers package the source and recipient info into a
:class:`HearsayDraft` rather than passing six positional arguments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph


@dataclass(frozen=True)
class HearsayDraft:
    """Immutable description of a single HEARSAY write.

    ``text``/``told_by``/``game_time`` describe the source fact; the
    ``recipient_id``/``recipient_location`` pair pins the listener.
    The frozen dataclass lets callers build one draft per recipient
    without positional-argument sprawl.
    """

    text: str
    told_by: UUID
    game_time: float
    recipient_id: UUID
    recipient_location: UUID


def write_hearsay_node(graph: KnowledgeGraph, draft: HearsayDraft) -> UUID:
    """Create one ``LOCAL`` ``HEARSAY`` node for ``draft.recipient_id`` and return its UUID.

    The recipient NPC does not get a direct edge to the node — the
    ``LOCAL`` scope + ``draft.recipient_location`` is enough for
    :class:`knowledge.query.KnowledgeQueryEngine` to surface it in
    that NPC's context. The only edge written is a ``TOLD_BY``
    provenance link from the new node back to ``draft.told_by`` (the
    original witness/source) so the chain of transmission stays
    auditable. ``draft.recipient_id`` is stored on that edge so
    tests and callers can trace "who heard this" without overloading
    the ``WITNESSED`` edge type.
    """
    hearsay = KnowledgeNode(
        text=draft.text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.HEARSAY,
        canon=CanonSource.SESSION,
        location_id=draft.recipient_location,
        timestamp=draft.game_time,
    )
    hearsay_id = graph.add_node(hearsay)
    graph.add_edge(
        hearsay_id,
        draft.told_by,
        EdgeType.TOLD_BY,
        metadata={"recipient_id": draft.recipient_id},
    )
    return hearsay_id
