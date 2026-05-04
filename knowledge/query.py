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

# Tuning for the salience+recency blend in ``get_memories_held_by``.
# ``W=0.7`` keeps the salience term dominant: a 0.95 pivotal memory
# beats a fresh 0.3 routine memory at every ``TAU`` age, then both
# decay symmetrically.
_SALIENCE_WEIGHT = 0.7
_RECENCY_WEIGHT = 1 - _SALIENCE_WEIGHT
_RECENCY_TAU_HOURS = 72.0
_FLOAT_ZERO = float(0)

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


def _now_reference(memories: list[KnowledgeNode]) -> float:
    """Pick the recency reference time for a result set.

    The query engine has no direct line on the game clock, so we use
    the freshest known timestamp in the candidate pool as "now". Any
    memory missing a timestamp drops to the oldest bucket and gets a
    zero recency contribution — its salience alone decides whether it
    survives the cut.
    """
    timestamps = [memory.timestamp for memory in memories if memory.timestamp is not None]
    if not timestamps:
        return _FLOAT_ZERO
    return max(timestamps)


def _memory_score(memory: KnowledgeNode, now: float) -> float:
    """Blend salience and recency into a single ranking score.

    ``recency_factor`` decays linearly over ``_RECENCY_TAU_HOURS`` so
    a memory older than the window contributes nothing from the
    recency side and is held up by salience alone. The blend is a
    convex combination — both terms live in ``[0, 1]`` and ``score``
    does too — which keeps the weights interpretable.
    """
    recency_factor = _FLOAT_ZERO
    if memory.timestamp is not None:
        age = max(_FLOAT_ZERO, now - memory.timestamp)
        recency_factor = max(_FLOAT_ZERO, 1 - age / _RECENCY_TAU_HOURS)
    return _SALIENCE_WEIGHT * memory.salience + _RECENCY_WEIGHT * recency_factor


def _rank_by_score(memories: list[KnowledgeNode]) -> list[KnowledgeNode]:
    """Sort *memories* in place by the salience+recency blend, newest-impactful first."""
    if not memories:
        return memories
    now = _now_reference(memories)
    memories.sort(key=lambda memory: _memory_score(memory, now), reverse=True)
    return memories


def _rank_and_limit(memories: list[KnowledgeNode], limit: int | None) -> list[KnowledgeNode]:
    """Rank *memories* by salience+recency and trim to *limit*; ``None`` returns every match."""
    ranked = _rank_by_score(memories)
    if limit is None:
        return ranked
    return ranked[:limit]


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
            query_filters.append_personal_memories(self._graph, filt.npc_id, matching_nodes)

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

    def get_memories_held_by(self, npc_id: UUID, limit: int = 5) -> list[KnowledgeNode]:
        """Return the NPC's PERSONAL_EXPERIENCE memories ranked by salience+recency.

        Pivotal events (high ``salience``) outrank trivial chatter even
        when the chatter is fresher, so a witnessed killing isn't
        crowded out of the top-K cut by an afternoon of small-talk
        summaries. Equal-salience memories fall back to recency
        ordering — the recency term still differentiates them.
        """
        return _rank_by_score(self._graph.personal_memories_for(npc_id))[:limit]

    def get_memories_about_subject(
        self,
        holder_id: UUID,
        subject_id: UUID,
        limit: int | None = None,
    ) -> list[KnowledgeNode]:
        """Return *holder_id*'s personal memories whose ``subject_id`` matches.

        Ranked with the same salience+recency blend as
        :meth:`get_memories_held_by`. ``limit=None`` returns every
        match; conversational prompts that only show the top-N can pass
        an explicit cap.
        """
        matched = [memory for memory in self._graph.personal_memories_for(holder_id) if memory.subject_id == subject_id]
        return _rank_and_limit(matched, limit)

    def get_memories_about_concept(
        self,
        holder_id: UUID,
        concept_tag: str,
        fuzzy_threshold: float = query_filters.CONCEPT_FUZZY_DEFAULT,
        limit: int | None = None,
    ) -> list[KnowledgeNode]:
        """Return *holder_id*'s personal memories whose ``tags`` match *concept_tag*.

        Concepts are abstract (``light_without_flame``,
        ``image_capture``) and have no canonical UUID, so this is the
        tag-keyed counterpart to :meth:`get_memories_about_subject`.
        A memory matches when *any* of its tags has similarity at or
        above ``fuzzy_threshold``; the comparator is
        :class:`difflib.SequenceMatcher` so a classifier emitting
        ``light_without_fire`` against a stored ``light_without_flame``
        still finds the prior encounter rather than starting the
        familiarity counter from zero. Comparison is case-insensitive
        and ranks by the same salience+recency blend as
        :meth:`get_memories_held_by`.
        """
        matched = [
            memory
            for memory in self._graph.personal_memories_for(holder_id)
            if query_filters.concept_tag_matches(memory.tags, concept_tag, fuzzy_threshold)
        ]
        return _rank_and_limit(matched, limit)
