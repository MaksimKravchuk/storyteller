"""Knowledge query engine — filters the graph for NPC-accessible knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import UUID

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource
from knowledge import query_filters

if TYPE_CHECKING:
    from models.character import Character

_DEFAULT_SORT_PRIORITY = 99

_SOURCE_PRIORITY = MappingProxyType(
    {
        KnowledgeSource.PERSONAL_EXPERIENCE: 0,
        KnowledgeSource.FACT: 1,
        KnowledgeSource.HEARSAY: 2,
        KnowledgeSource.RUMOR: 3,
    }
)

_SOURCE_PREFIXES = MappingProxyType(
    {
        KnowledgeSource.RUMOR: "[Rumour] ",
        KnowledgeSource.HEARSAY: "[Heard from someone] ",
        KnowledgeSource.PERSONAL_EXPERIENCE: "[Personal experience] ",
    }
)


@dataclass
class KnowledgeFilter:
    """Filter criteria for querying the knowledge graph."""

    max_scope: KnowledgeScope = KnowledgeScope.WORLD
    max_education_required: int = 10
    location_id: UUID | None = None
    npc_id: UUID | None = None  # Include personal memories for this NPC


def _node_matches(node: KnowledgeNode, filt: KnowledgeFilter) -> bool:
    """Return True if a node passes all filter criteria."""
    checks = (
        query_filters.passes_scope(node, filt.max_scope),
        query_filters.passes_education(node, filt.max_education_required),
        query_filters.passes_location(node, filt.location_id),
    )
    return all(checks)


def _memory_sort_key(node: KnowledgeNode) -> float:
    """Return the timestamp of a memory node for sorting, treating missing as oldest."""
    if node.timestamp is None:
        return float("-inf")
    return node.timestamp


class KnowledgeQueryEngine:
    """Applies filters to the knowledge graph for NPC-aware retrieval.

    The core idea: each NPC can only access a *subset* of world knowledge
    determined by their education level, social status, location, and scope.
    A peasant knows local gossip; a scholar knows foreign politics.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def query(self, filt: KnowledgeFilter) -> list[KnowledgeNode]:
        """Return all knowledge nodes matching ``filt``."""
        matching_nodes = [node for node in self._graph.all_nodes() if _node_matches(node, filt)]

        if filt.npc_id:
            self._add_personal_memories(filt.npc_id, matching_nodes)

        return matching_nodes

    def build_npc_filter(self, npc: Character) -> KnowledgeFilter:
        """Build a KnowledgeFilter from an NPC's attributes.

        Attribute mapping:
          - ``education`` (0-10) → max_education_required
          - ``knowledge_scope`` → max_scope
          - ``location_id`` → location_id
        """
        scope_map = {
            "local": KnowledgeScope.LOCAL,
            "city": KnowledgeScope.CITY,
            "region": KnowledgeScope.REGION,
            "country": KnowledgeScope.COUNTRY,
            "world": KnowledgeScope.WORLD,
        }
        return KnowledgeFilter(
            max_scope=scope_map.get(npc.knowledge_scope, KnowledgeScope.LOCAL),
            max_education_required=npc.get_attribute("education", 3),
            location_id=npc.location_id,
            npc_id=npc.uuid,
        )

    def get_context_for_npc(self, npc: Character) -> str:
        """Return a formatted text block of knowledge accessible to this NPC.

        This string is injected into the Actor's system prompt so the NPC
        only knows what it should know.
        """
        npc_filter = self.build_npc_filter(npc)
        nodes = self.query(npc_filter)
        if not nodes:
            return "You don't have any specific knowledge about this topic."

        nodes.sort(key=lambda node: _SOURCE_PRIORITY.get(node.source, _DEFAULT_SORT_PRIORITY))
        lines = [f"- {_SOURCE_PREFIXES.get(node.source, '')}{node.text}" for node in nodes]
        return "\n".join(lines)

    def get_memories_about(self, npc_id: UUID, limit: int = 5) -> list[KnowledgeNode]:
        """Return the NPC's most recent PERSONAL_EXPERIENCE memories, newest first."""
        memories = self._personal_memories_for(npc_id)
        memories.sort(key=_memory_sort_key, reverse=True)
        return memories[:limit]

    def _personal_memories_for(self, npc_id: UUID) -> list[KnowledgeNode]:
        """Return every PERSONAL_EXPERIENCE node linked from *npc_id*."""
        linked_ids = {target_id for target_id, _ in self._graph.get_edges_from(npc_id)}
        if not linked_ids:
            return []
        return [
            node
            for node in self._graph.all_nodes()
            if node.source == KnowledgeSource.PERSONAL_EXPERIENCE and node.uuid in linked_ids
        ]

    def _add_personal_memories(self, npc_id: UUID, matching_nodes: list[KnowledgeNode]) -> None:
        """Append personal-experience nodes linked to *npc_id* that aren't already included."""
        existing_ids = {node.uuid for node in matching_nodes}
        for memory in self._personal_memories_for(npc_id):
            if memory.uuid not in existing_ids:
                matching_nodes.append(memory)
