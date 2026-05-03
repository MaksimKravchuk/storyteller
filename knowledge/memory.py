"""Memory manager — creates knowledge nodes from interactions and events."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from models.game_state import INITIAL_GAME_CLOCK, PlayerState

from knowledge import salience as salience_presets
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


@dataclass(frozen=True)
class MemoryEvent:
    """Inputs for :meth:`MemoryManager.create_memory_from_event`.

    ``salience`` defaults to the neutral preset; combat / overheard /
    event sites pick a tuned value from :mod:`knowledge.salience`.
    """

    event_description: str
    witness_ids: list[UUID]
    scope: KnowledgeScope
    location_id: UUID | None = None
    game_time: float = INITIAL_GAME_CLOCK
    salience: float = salience_presets.DEFAULT


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
        salience: float = salience_presets.ROUTINE_DIALOGUE,
    ) -> None:
        """Summarise many interactions concurrently into memory nodes.

        Each ``pair`` is ``(npc_id, interaction_log)``. Both the
        targeted-dialogue path and the retaliation path feed this
        helper so a single turn issues one concurrent gather for all
        NPC memories. ``salience`` is the importance score stamped on
        every produced memory — the retaliation path overrides the
        default since a fight an NPC was dragged into matters more
        than ordinary chitchat.
        """
        if not pairs:
            return
        await asyncio.gather(
            *(
                self._summarize_one(
                    interaction_log=log,
                    npc_id=npc_id,
                    game_time=game_time,
                    salience=salience,
                )
                for npc_id, log in pairs
            ),
        )

    async def create_memory_from_event(self, event: MemoryEvent) -> list[UUID]:
        """Create memory nodes for all witnesses of an event.

        Scope determines how the memory propagates:
          - LOCAL: only witnesses get PERSONAL_EXPERIENCE
          - CITY/REGION: becomes RUMOR accessible in that area
          - WORLD: becomes FACT accessible broadly

        ``event.salience`` is stamped on every created node so the
        recall layer can rank pivotal events (combat, deaths, big
        reveals) above routine chatter. Callers should reach into
        :mod:`knowledge.salience` for the right preset.

        Returns list of created node UUIDs. The first entry is
        canonical across per-witness duplicates, so callers where the
        player was subject or witness may pass the list to
        :func:`record_player_learned_fact`.
        """
        if event.scope == KnowledgeScope.LOCAL:
            return self._create_local_witness_memories(event)
        return self._create_broadcast_with_witnesses(event)

    def _create_local_witness_memories(self, event: MemoryEvent) -> list[UUID]:
        """LOCAL-scope path: one PERSONAL_EXPERIENCE node per witness."""
        return [self._add_personal_witness_memory(event, witness_id) for witness_id in event.witness_ids]

    def _create_broadcast_with_witnesses(self, event: MemoryEvent) -> list[UUID]:
        """CITY+ scope path: one broadcast node plus per-witness personal copies."""
        broadcast_source = KnowledgeSource.FACT if event.scope >= KnowledgeScope.COUNTRY else KnowledgeSource.RUMOR
        broadcast_id = self._graph.add_node(
            KnowledgeNode(
                text=event.event_description,
                scope=event.scope,
                source=broadcast_source,
                canon=CanonSource.SESSION,
                location_id=event.location_id,
                timestamp=event.game_time,
                salience=event.salience,
            ),
        )
        personal_ids = (self._add_personal_witness_memory(event, witness_id) for witness_id in event.witness_ids)
        return [broadcast_id, *personal_ids]

    def _add_personal_witness_memory(self, event: MemoryEvent, witness_id: UUID) -> UUID:
        """Add a LOCAL ``PERSONAL_EXPERIENCE`` node and link it to ``witness_id``."""
        node_id = self._graph.add_node(
            KnowledgeNode(
                text=event.event_description,
                scope=KnowledgeScope.LOCAL,
                source=KnowledgeSource.PERSONAL_EXPERIENCE,
                canon=CanonSource.SESSION,
                location_id=event.location_id,
                timestamp=event.game_time,
                salience=event.salience,
            ),
        )
        self._graph.add_edge(witness_id, node_id, EdgeType.WITNESSED)
        return node_id

    async def _summarize_one(
        self,
        interaction_log: str,
        npc_id: UUID,
        game_time: float,
        salience: float,
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
            timestamp=game_time,
            salience=salience,
        )
        node_id = self._graph.add_node(node)

        if npc_id in self._graph.digraph:
            self._graph.add_edge(npc_id, node_id, EdgeType.WITNESSED)
