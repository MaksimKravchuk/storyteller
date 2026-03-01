"""Memory manager — creates knowledge nodes from interactions and events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from knowledge.graph import KnowledgeGraph
from knowledge.node import (
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)

if TYPE_CHECKING:
    from llm.base_client import BaseLLMClient
    from models.npc_card import NPCCard


class MemoryManager:
    """Creates and manages memory nodes from in-game interactions.

    Uses the LLM to summarise conversations and events into compact
    knowledge nodes that are stored in the graph.
    """

    def __init__(
        self,
        graph: KnowledgeGraph,
        llm_client: BaseLLMClient,
    ) -> None:
        self._graph = graph
        self._llm = llm_client

    async def summarize_interaction(
        self,
        interaction_log: str,
        npc_id: str,
        game_time: float = 0.0,
    ) -> KnowledgeNode:
        """Summarise an interaction into a memory node linked to an NPC.

        The LLM extracts: what the NPC learned, emotional impression,
        and key facts exchanged.
        """
        from llm.message import Message, Role

        prompt = (
            "Summarise the following conversation from the NPC's perspective "
            "in 1-2 sentences. Focus on: what did the NPC learn? "
            "What is their impression of the player? "
            "Also rate the emotional valence of this interaction from -1.0 "
            "(very negative) to 1.0 (very positive).\n"
            "Output JSON: {\"summary\": \"...\", \"valence\": 0.0}\n\n"
            f"{interaction_log}"
        )
        response = await self._llm.send_message(
            messages=[Message(role=Role.USER, content=prompt)],
            system_prompt="You are a memory summariser for a text adventure game. "
            "Output only valid JSON.",
            max_tokens=200,
        )

        # Try to parse JSON, fall back to raw text
        import json
        valence = 0.0
        summary = response.content.strip()
        try:
            data = json.loads(summary)
            summary = data.get("summary", summary)
            valence = float(data.get("valence", 0.0))
        except (json.JSONDecodeError, ValueError):
            pass

        node = KnowledgeNode(
            content=summary,
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            timestamp=game_time,
            emotional_valence=valence,
            decay_rate=0.005,  # Slowly fades over ~200 game-hours
        )
        node_id = self._graph.add_node(node)

        # Link the memory to the NPC
        if npc_id in [n for n in self._graph._graph.nodes]:
            self._graph.add_edge(npc_id, node_id, EdgeType.WITNESSED)

        return node

    async def create_memory_from_event(
        self,
        event_description: str,
        witness_ids: list[str],
        scope: KnowledgeScope,
        location_id: str | None = None,
        game_time: float = 0.0,
    ) -> list[str]:
        """Create memory nodes for all witnesses of an event.

        Scope determines how the memory propagates:
          - LOCAL: only witnesses get PERSONAL_EXPERIENCE
          - CITY/REGION: becomes RUMOR accessible in that area
          - WORLD: becomes FACT accessible broadly

        Returns list of created node UUIDs.
        """
        created_ids: list[str] = []

        if scope == KnowledgeScope.LOCAL:
            # Personal memories for each witness
            for witness_id in witness_ids:
                node = KnowledgeNode(
                    content=event_description,
                    scope=KnowledgeScope.LOCAL,
                    source=KnowledgeSource.PERSONAL_EXPERIENCE,
                    location_id=location_id,
                    timestamp=game_time,
                    decay_rate=0.005,
                )
                node_id = self._graph.add_node(node)
                self._graph.add_edge(witness_id, node_id, EdgeType.WITNESSED)
                created_ids.append(node_id)
        else:
            # Wider-scope events become rumours or facts
            source = (
                KnowledgeSource.FACT
                if scope >= KnowledgeScope.COUNTRY
                else KnowledgeSource.RUMOR
            )
            node = KnowledgeNode(
                content=event_description,
                scope=scope,
                source=source,
                location_id=location_id,
                timestamp=game_time,
            )
            node_id = self._graph.add_node(node)
            created_ids.append(node_id)

            # Also give witnesses a personal memory
            for witness_id in witness_ids:
                personal = KnowledgeNode(
                    content=event_description,
                    scope=KnowledgeScope.LOCAL,
                    source=KnowledgeSource.PERSONAL_EXPERIENCE,
                    location_id=location_id,
                    timestamp=game_time,
                    decay_rate=0.005,
                )
                personal_id = self._graph.add_node(personal)
                self._graph.add_edge(witness_id, personal_id, EdgeType.WITNESSED)
                created_ids.append(personal_id)

        return created_ids

    def create_belief(
        self,
        npc_id: str,
        content: str,
        confidence: float = 0.7,
        emotional_valence: float = 0.0,
        game_time: float = 0.0,
    ) -> str:
        """Create a BELIEF-sourced knowledge node linked to an NPC.

        Beliefs are subjective and may contradict facts. They are only
        accessible to the NPC they belong to.

        Returns the created node UUID.
        """
        node = KnowledgeNode(
            content=content,
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.BELIEF,
            timestamp=game_time,
            confidence=confidence,
            emotional_valence=emotional_valence,
            decay_rate=0.002,  # Beliefs fade very slowly
        )
        node_id = self._graph.add_node(node)

        # Link to the NPC
        if npc_id in [n for n in self._graph._graph.nodes]:
            self._graph.add_edge(npc_id, node_id, EdgeType.KNOWS_ABOUT)

        return node_id

    @staticmethod
    def update_emotional_attitude(
        npc: NPCCard,
        target_id: str,
        emotion: str,
        delta: float,
    ) -> None:
        """Adjust an NPC's emotional attitude toward a character.

        Emotions are clamped to [-1.0, 1.0].
        Valid emotions: trust, fear, gratitude, resentment, respect,
        contempt, affection, suspicion.
        """
        if target_id not in npc.emotional_attitudes:
            npc.emotional_attitudes[target_id] = {}
        current = npc.emotional_attitudes[target_id].get(emotion, 0.0)
        npc.emotional_attitudes[target_id][emotion] = max(
            -1.0, min(1.0, current + delta)
        )
