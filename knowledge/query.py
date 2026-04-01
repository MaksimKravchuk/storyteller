"""Knowledge query engine — filters the graph for NPC-accessible knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource

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
    max_social_status_required: int = 10
    location_id: str | None = None
    tags: list[str] | None = None
    sources: list[KnowledgeSource] | None = None
    npc_id: str | None = None  # Include personal memories for this NPC


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
        matching_nodes: list[KnowledgeNode] = []

        for node in self._graph.all_nodes():
            # Scope check: node scope must be ≤ filter's max scope
            if node.scope > filt.max_scope:
                continue

            # Education gate
            if node.required_education > filt.max_education_required:
                continue

            # Social status gate
            if node.required_social_status > filt.max_social_status_required:
                continue

            # Location filter (if specified)
            if filt.location_id and node.location_id:
                # Local-scope nodes only visible if location matches
                if node.scope == KnowledgeScope.LOCAL:
                    if node.location_id != filt.location_id:
                        continue

            # Tag filter (if specified): at least one tag must match
            if filt.tags:
                if not (set(filt.tags) & set(node.tags)):
                    continue

            # Source filter
            if filt.sources:
                if node.source not in filt.sources:
                    continue

            matching_nodes.append(node)

        # If npc_id is set, also include personal memories linked to that NPC
        if filt.npc_id:
            for node in self._graph.all_nodes():
                if node.source == KnowledgeSource.PERSONAL_EXPERIENCE:
                    # Check if this memory is linked to the NPC via edges
                    edges = self._graph.get_edges_from(filt.npc_id)
                    for target_id, _ in edges:
                        if target_id == node.uuid and node not in matching_nodes:
                            matching_nodes.append(node)

        return matching_nodes

    def build_npc_filter(self, npc: Character) -> KnowledgeFilter:
        """Build a KnowledgeFilter from an NPC's attributes.

        Attribute mapping:
          - ``education`` (0-10) → max_education_required
          - ``social_status`` (0-10) → max_social_status_required
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
            max_social_status_required=npc.get_attribute("social_status", 3),
            location_id=npc.location_id,
            npc_id=npc.uuid,
        )

    def get_context_for_npc(
        self,
        npc: Character,
        topic_tags: list[str] | None = None,
    ) -> str:
        """Return a formatted text block of knowledge accessible to this NPC.

        This string is injected into the Actor's system prompt so the NPC
        only knows what it should know.
        """
        npc_filter = self.build_npc_filter(npc)
        if topic_tags:
            npc_filter.tags = topic_tags

        nodes = self.query(npc_filter)
        if not nodes:
            return "You don't have any specific knowledge about this topic."

        nodes.sort(key=lambda node: _SOURCE_PRIORITY.get(node.source, _DEFAULT_SORT_PRIORITY))
        lines = [f"- {_SOURCE_PREFIXES.get(node.source, '')}{node.content}" for node in nodes]
        return "\n".join(lines)
