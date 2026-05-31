"""Actor memory selection and non-personal knowledge formatting."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any
from uuid import UUID

from cast._npc_active_goal import select_active_goal
from knowledge.node import KnowledgeNode, KnowledgeSource
from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState
from models.npc_card import NPCCard

_DEFAULT_SORT_PRIORITY = 99
_KNOWLEDGE_FALLBACK = "You don't have any specific knowledge about this topic."
_SOURCE_PRIORITY = MappingProxyType(
    {
        KnowledgeSource.FACT: 1,
        KnowledgeSource.HEARSAY: 2,
        KnowledgeSource.RUMOR: 3,
    }
)
_SOURCE_PREFIXES = MappingProxyType(
    {
        KnowledgeSource.RUMOR: "[Rumour] ",
        KnowledgeSource.HEARSAY: "[Heard from someone] ",
    }
)


def format_accessible_knowledge(knowledge_query: KnowledgeQueryEngine, npc: NPCCard) -> str:
    """Render non-personal knowledge for the Actor prompt."""
    filt = knowledge_query.build_npc_filter(npc)
    nodes: list[KnowledgeNode] = []
    for knowledge_node in knowledge_query.query(filt):
        if knowledge_node.source != KnowledgeSource.PERSONAL_EXPERIENCE:
            nodes.append(knowledge_node)
    if not nodes:
        return _KNOWLEDGE_FALLBACK
    nodes.sort(key=_knowledge_sort_key)
    return "\n".join(_knowledge_line(node_entry) for node_entry in nodes)


def select_actor_memories(
    npc: NPCCard,
    knowledge_query: KnowledgeQueryEngine,
    context: dict[str, Any],
    limit: int = 5,
) -> list[KnowledgeNode]:
    """Return the relevant memories to render into an Actor prompt."""
    selector = _MemorySelector(npc, knowledge_query, context)
    return selector.select(limit)


class _MemorySelector:
    def __init__(self, npc: NPCCard, knowledge_query: KnowledgeQueryEngine, context: dict[str, Any]) -> None:
        self._npc = npc
        self._knowledge_query = knowledge_query
        self._context = context

    def select(self, limit: int) -> list[KnowledgeNode]:
        scoped_memories = self._scoped_memories()
        if scoped_memories:
            return _dedupe_memories(scoped_memories)[:limit]
        return self._knowledge_query.get_memories_held_by(self._npc.uuid, limit=limit)

    def _scoped_memories(self) -> list[KnowledgeNode]:
        memories: list[KnowledgeNode] = []
        if self._context.get("is_npc_turn"):
            goal = select_active_goal(self._npc)
            if goal is not None and goal.target_uuid is not None:
                memories.extend(self._subject_memories(goal.target_uuid))
        player_id = self._player_uuid()
        if player_id is not None:
            memories.extend(self._subject_memories(player_id))
        for tag in self._memory_concept_tags():
            memories.extend(self._knowledge_query.get_memories_about_concept(self._npc.uuid, tag))
        return memories

    def _subject_memories(self, subject_id: UUID) -> list[KnowledgeNode]:
        return self._knowledge_query.get_memories_about_subject(self._npc.uuid, subject_id)

    def _player_uuid(self) -> UUID | None:
        game_state = self._context.get("game_state")
        if isinstance(game_state, GameState):
            return game_state.player.uuid
        player_uuid = self._context.get("player_uuid")
        if isinstance(player_uuid, UUID):
            return player_uuid
        return None

    def _memory_concept_tags(self) -> list[str]:
        raw_tags = self._context.get("memory_concept_tags")
        if raw_tags is None:
            return []
        if isinstance(raw_tags, str):
            return [raw_tags]
        return [str(tag) for tag in raw_tags if str(tag).strip()]


def _knowledge_sort_key(knowledge_node: KnowledgeNode) -> int:
    return _SOURCE_PRIORITY.get(knowledge_node.source, _DEFAULT_SORT_PRIORITY)


def _knowledge_line(knowledge_node: KnowledgeNode) -> str:
    prefix = _SOURCE_PREFIXES.get(knowledge_node.source, "")
    return "- {0}{1}".format(prefix, knowledge_node.text)


def _dedupe_memories(memories: list[KnowledgeNode]) -> list[KnowledgeNode]:
    seen_ids: set[UUID] = set()
    unique: list[KnowledgeNode] = []
    for memory in memories:
        if memory.uuid in seen_ids:
            continue
        seen_ids.add(memory.uuid)
        unique.append(memory)
    return unique
