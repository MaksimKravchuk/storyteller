"""Memory manager — creates knowledge nodes from interactions and events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from models.game_state import INITIAL_GAME_CLOCK

from knowledge.graph import KnowledgeGraph
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)

if TYPE_CHECKING:
    from llm.base_client import BaseLLMClient

_SUMMARY_MAX_TOKENS = 200


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
        game_time: float = INITIAL_GAME_CLOCK,
    ) -> KnowledgeNode:
        """Summarise an interaction into a memory node linked to an NPC.

        The LLM extracts: what the NPC learned, emotional impression,
        and key facts exchanged.
        """
        from llm.message import Message, Role

        prompt = (
            "Summarise the following conversation from the NPC's perspective "
            "in 1-2 sentences. Focus on: what did the NPC learn? "
            "What is their impression of the player?\n\n"
            f"{interaction_log}"
        )
        response = await self._llm.send_message(
            messages=[Message(role=Role.USER, body=prompt)],
            system_prompt="You are a memory summariser for a text adventure game. "
            "Output only the summary, nothing else.",
            max_tokens=_SUMMARY_MAX_TOKENS,
        )

        node = KnowledgeNode(
            text=response.body.strip(),
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            canon=CanonSource.SESSION,
            timestamp=game_time,
        )
        node_id = self._graph.add_node(node)

        # Link the memory to the NPC
        if npc_id in [node_id for node_id in self._graph.digraph.nodes]:
            self._graph.add_edge(npc_id, node_id, EdgeType.WITNESSED)

        return node

    async def create_memory_from_event(
        self,
        event_description: str,
        witness_ids: list[str],
        scope: KnowledgeScope,
        location_id: str | None = None,
        game_time: float = INITIAL_GAME_CLOCK,
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
            for witness_id in witness_ids:
                node_id = self._graph.add_node(
                    KnowledgeNode(
                        text=event_description,
                        scope=KnowledgeScope.LOCAL,
                        source=KnowledgeSource.PERSONAL_EXPERIENCE,
                        canon=CanonSource.SESSION,
                        location_id=location_id,
                        timestamp=game_time,
                    )
                )
                self._graph.add_edge(witness_id, node_id, EdgeType.WITNESSED)
                created_ids.append(node_id)
        else:
            created_ids.append(
                self._graph.add_node(
                    KnowledgeNode(
                        text=event_description,
                        scope=scope,
                        source=KnowledgeSource.FACT if scope >= KnowledgeScope.COUNTRY else KnowledgeSource.RUMOR,
                        canon=CanonSource.SESSION,
                        location_id=location_id,
                        timestamp=game_time,
                    )
                )
            )

            # Also give witnesses a personal memory
            for witness_id in witness_ids:
                personal = KnowledgeNode(
                    text=event_description,
                    scope=KnowledgeScope.LOCAL,
                    source=KnowledgeSource.PERSONAL_EXPERIENCE,
                    canon=CanonSource.SESSION,
                    location_id=location_id,
                    timestamp=game_time,
                )
                personal_id = self._graph.add_node(personal)
                self._graph.add_edge(witness_id, personal_id, EdgeType.WITNESSED)
                created_ids.append(personal_id)

        return created_ids
