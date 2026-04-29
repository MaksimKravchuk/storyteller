"""Filter predicate functions for the knowledge query engine."""

from __future__ import annotations

from knowledge.node import KnowledgeNode, KnowledgeScope


def passes_scope(node: KnowledgeNode, max_scope: KnowledgeScope) -> bool:
    """Return True if the node's scope is within the given max scope."""
    return node.scope <= max_scope


def passes_education(node: KnowledgeNode, max_education_required: int) -> bool:
    """Return True if the node's education requirement is within the limit."""
    return node.required_education <= max_education_required


def passes_social_status(node: KnowledgeNode, max_social_status_required: int) -> bool:
    """Return True if the node's social status requirement is within the limit."""
    return node.required_social_status <= max_social_status_required


def passes_location(
    node: KnowledgeNode,
    location_id: str | None,
) -> bool:
    """Local-scope nodes are only visible when their location matches."""
    if not location_id or not node.location_id:
        return True
    if node.scope == KnowledgeScope.LOCAL:
        return node.location_id == location_id
    return True
