"""Filter predicate functions for the knowledge query engine."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING
from uuid import UUID

from knowledge.node import EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph

_RECIPIENT_ID_KEY = "recipient_id"
_MISSING_RECIPIENT = object()


def passes_scope(node: KnowledgeNode, max_scope: KnowledgeScope) -> bool:
    """Return True if the node's scope is within the given max scope."""
    return node.scope <= max_scope


def passes_education(node: KnowledgeNode, max_education_required: int) -> bool:
    """Return True if the node's education requirement is within the limit."""
    return node.required_education <= max_education_required


def passes_location(
    node: KnowledgeNode,
    location_id: UUID | None,
) -> bool:
    """Local-scope nodes are only visible when their location matches."""
    if not location_id or not node.location_id:
        return True
    if node.scope == KnowledgeScope.LOCAL:
        return node.location_id == location_id
    return True


def passes_hearsay_ownership(
    graph: KnowledgeGraph,
    node: KnowledgeNode,
    npc_id: UUID | None,
) -> bool:
    """Return whether a HEARSAY node is visible to ``npc_id`` under ownership metadata."""
    if node.source != KnowledgeSource.HEARSAY:
        return True
    if npc_id is None:
        return True
    owned_recipients = _hearsay_recipient_ids(graph, node.uuid)
    if not owned_recipients:
        return True
    return any(str(recipient_id) == str(npc_id) for recipient_id in owned_recipients)


def _hearsay_recipient_ids(graph: KnowledgeGraph, hearsay_id: UUID) -> list[object]:
    recipient_ids: list[object] = []
    for target_id, edge_type in graph.get_edges_from(hearsay_id):
        if edge_type != EdgeType.TOLD_BY:
            continue
        metadata = graph.get_edge_metadata(hearsay_id, target_id)
        recipient_id = metadata.get(_RECIPIENT_ID_KEY, _MISSING_RECIPIENT)
        if recipient_id is not _MISSING_RECIPIENT:
            recipient_ids.append(recipient_id)
    return recipient_ids


def concept_tag_matches(tags: list[str], target: str, threshold: float) -> bool:
    """Return True if any of *tags* is similar enough to *target*.

    Comparison is case-insensitive via :class:`difflib.SequenceMatcher`
    so a classifier emitting ``light_without_fire`` against a stored
    ``light_without_flame`` still finds the prior encounter rather than
    starting the familiarity counter from zero.
    """
    folded_target = target.casefold()
    for tag in tags:
        if SequenceMatcher(a=tag.casefold(), b=folded_target).ratio() >= threshold:
            return True
    return False


def append_personal_memories(
    graph: KnowledgeGraph,
    npc_id: UUID,
    matching_nodes: list[KnowledgeNode],
) -> None:
    """Append *npc_id*'s personal-experience nodes that aren't already in the result list."""
    existing_ids = {node.uuid for node in matching_nodes}
    for memory in graph.personal_memories_for(npc_id):
        if memory.uuid not in existing_ids:
            matching_nodes.append(memory)
