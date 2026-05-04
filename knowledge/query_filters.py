"""Filter predicate functions for the knowledge query engine."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING
from uuid import UUID

from knowledge.node import KnowledgeNode, KnowledgeScope

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph

# Default similarity threshold for ``concept_tag_matches``. Calibrated
# against snake_case concept slugs where a single token substitution
# (``light_without_flame`` vs ``light_without_fire``) scores ~0.86 with
# ``difflib.SequenceMatcher`` — at 0.85 the pair matches without sweeping
# in unrelated concepts that share only a common prefix.
CONCEPT_FUZZY_DEFAULT = 0.85


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


def concept_tag_matches(tags: list[str], target: str, threshold: float = CONCEPT_FUZZY_DEFAULT) -> bool:
    """Return True if any of *tags* is similar enough to *target*.

    Comparison is case-insensitive. The exact-match short-circuit handles
    the common path (a classifier reusing the seed identifier) in a single
    hash lookup; the SequenceMatcher fallback only runs when the
    classifier drifts (``light_without_fire`` against stored
    ``light_without_flame``). ``autojunk=False`` keeps the ratio honest
    on short snake_case slugs where the heuristic would otherwise treat
    repeated chars as junk.
    """
    folded_target = target.casefold()
    folded_tags = [tag.casefold() for tag in tags]
    if folded_target in folded_tags:
        return True
    for folded_tag in folded_tags:
        if SequenceMatcher(a=folded_tag, b=folded_target, autojunk=False).ratio() >= threshold:
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
