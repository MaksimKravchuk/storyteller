"""Knowledge query engine — filters the graph for NPC-accessible knowledge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource

if TYPE_CHECKING:
    from models.character import Character


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

    def query(
        self,
        filt: KnowledgeFilter,
        current_time: float | None = None,
    ) -> list[KnowledgeNode]:
        """Return all knowledge nodes matching ``filt``.

        If ``current_time`` is given, nodes with a decay_rate > 0 have
        their effective confidence computed; nodes that have decayed
        below 0.1 are excluded.
        """
        results: list[KnowledgeNode] = []

        for node in self._graph.all_nodes():
            # Skip non-KnowledgeNode entries (e.g. NPC refs stored in the graph)
            if not isinstance(node, KnowledgeNode):
                continue

            # Decay check
            if current_time is not None and node.decay_rate > 0 and node.timestamp is not None:
                elapsed = current_time - node.timestamp
                effective_confidence = node.confidence - node.decay_rate * elapsed
                if effective_confidence < 0.1:
                    continue

            # Scope check: node scope must be <= filter's max scope
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

            results.append(node)

        # If npc_id is set, also include personal memories and beliefs
        if filt.npc_id:
            personal_sources = {
                KnowledgeSource.PERSONAL_EXPERIENCE,
                KnowledgeSource.BELIEF,
            }
            for node in self._graph.all_nodes():
                if not isinstance(node, KnowledgeNode):
                    continue
                if node.source in personal_sources:
                    # Check if this memory is linked to the NPC via edges
                    edges = self._graph.get_edges_from(filt.npc_id)
                    for target_id, _ in edges:
                        if target_id == node.uuid and node not in results:
                            # Decay check for personal memories too
                            if current_time is not None and node.decay_rate > 0 and node.timestamp is not None:
                                elapsed = current_time - node.timestamp
                                if node.confidence - node.decay_rate * elapsed < 0.1:
                                    continue
                            results.append(node)

        return results

    def build_npc_filter(self, npc: Character) -> KnowledgeFilter:
        """Build a KnowledgeFilter from an NPC's attributes.

        Attribute mapping:
          - ``education`` (0-10) -> max_education_required
          - ``social_status`` (0-10) -> max_social_status_required
          - ``knowledge_scope`` -> max_scope
          - ``location_id`` -> location_id
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
        current_time: float | None = None,
    ) -> str:
        """Return a formatted text block of knowledge accessible to this NPC.

        This string is injected into the Actor's system prompt so the NPC
        only knows what it should know.
        """
        filt = self.build_npc_filter(npc)
        if topic_tags:
            filt.tags = topic_tags

        nodes = self.query(filt, current_time=current_time)
        if not nodes:
            return "You don't have any specific knowledge about this topic."

        # Sort: personal experience first, then beliefs, then facts, then rumours
        source_priority = {
            KnowledgeSource.PERSONAL_EXPERIENCE: 0,
            KnowledgeSource.BELIEF: 1,
            KnowledgeSource.FACT: 2,
            KnowledgeSource.HEARSAY: 3,
            KnowledgeSource.RUMOR: 4,
        }
        nodes.sort(key=lambda n: source_priority.get(n.source, 99))

        lines: list[str] = []
        for node in nodes:
            prefix = ""
            if node.source == KnowledgeSource.RUMOR:
                prefix = "[Rumour] "
            elif node.source == KnowledgeSource.HEARSAY:
                prefix = "[Heard from someone] "
            elif node.source == KnowledgeSource.PERSONAL_EXPERIENCE:
                prefix = "[Personal experience] "
            elif node.source == KnowledgeSource.BELIEF:
                prefix = "[You believe] "
            lines.append(f"- {prefix}{node.content}")

        # Append emotional attitudes if the NPC has them
        if hasattr(npc, "emotional_attitudes") and npc.emotional_attitudes:
            lines.append("")
            lines.append("Your feelings about people you've interacted with:")
            for char_id, emotions in npc.emotional_attitudes.items():
                emo_parts = [
                    f"{k}={v:.1f}" for k, v in emotions.items() if abs(v) > 0.1
                ]
                if emo_parts:
                    lines.append(f"  - {char_id}: {', '.join(emo_parts)}")

        return "\n".join(lines)
