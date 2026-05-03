"""Memory manager — creates knowledge nodes from interactions and events."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from models.game_state import INITIAL_GAME_CLOCK, PlayerState

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


def record_player_learned_fact(player: PlayerState, created_ids: list[UUID]) -> None:
    """Attach the first created memory UUID to ``player.learned_facts``.

    All per-witness nodes produced by LOCAL-scope
    :meth:`MemoryManager.create_memory_from_event` share the same
    ``event_description``, so a single representative UUID is enough
    for the Character sidebar to render a ``RememberedFact``.
    """
    if created_ids:
        player.learned_facts.add(created_ids[0])


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

    async def summarize_interactions_batch(
        self,
        pairs: list[tuple[UUID, str]],
        game_time: float = INITIAL_GAME_CLOCK,
        location_id: UUID | None = None,
    ) -> None:
        """Summarise many interactions concurrently into memory nodes.

        Each ``pair`` is ``(npc_id, interaction_log)``. Both the
        targeted-dialogue path and the retaliation path feed this
        helper so a single turn issues one concurrent gather for all
        NPC memories.
        """
        if not pairs:
            return
        await asyncio.gather(
            *(
                self._summarize_one(
                    interaction_log=log,
                    npc_id=npc_id,
                    game_time=game_time,
                    location_id=location_id,
                )
                for npc_id, log in pairs
            ),
        )

    async def create_memory_from_event(
        self,
        event_description: str,
        witness_ids: list[UUID],
        scope: KnowledgeScope,
        location_id: UUID | None = None,
        game_time: float = INITIAL_GAME_CLOCK,
    ) -> list[UUID]:
        """Create memory nodes for all witnesses of an event.

        Scope determines how the memory propagates:
          - LOCAL: only witnesses get PERSONAL_EXPERIENCE
          - CITY/REGION: becomes RUMOR accessible in that area
          - WORLD: becomes FACT accessible broadly

        Returns list of created node UUIDs. The first entry is
        canonical across per-witness duplicates, so callers where the
        player was subject or witness may pass the list to
        :func:`record_player_learned_fact`.
        """
        created_ids: list[UUID] = []

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

    async def _summarize_one(
        self,
        interaction_log: str,
        npc_id: UUID,
        game_time: float,
        location_id: UUID | None = None,
    ) -> None:
        """Summarise a single interaction into a memory node linked to an NPC."""
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
            location_id=location_id,
            timestamp=game_time,
        )
        node_id = self._graph.add_node(node)

        if npc_id in self._graph.digraph:
            self._graph.add_edge(npc_id, node_id, EdgeType.WITNESSED)
