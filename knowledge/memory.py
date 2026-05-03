"""Memory manager — creates knowledge nodes from interactions and events."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
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


@dataclass(frozen=True)
class MemoryEventResult:
    """Outcome of :meth:`MemoryManager.create_memory_from_event`.

    ``canonical_id`` is the broadcast node for non-LOCAL scopes, the
    first per-witness node for LOCAL, and ``None`` only when no nodes
    were created. ``all_ids`` carries every created node id in creation
    order.
    """

    canonical_id: UUID | None
    all_ids: tuple[UUID, ...] = ()


def record_player_learned_fact(player: PlayerState, canonical_id: UUID | None) -> None:
    if canonical_id is not None:
        player.learned_facts.add(canonical_id)


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
    ) -> MemoryEventResult:
        """Create memory nodes for all witnesses of an event.

        Scope determines how the memory propagates:
          - LOCAL: only witnesses get PERSONAL_EXPERIENCE
          - CITY/REGION: becomes RUMOR accessible in that area
          - WORLD: becomes FACT accessible broadly
        """
        if scope == KnowledgeScope.LOCAL:
            return self._create_local_memory(
                event_description=event_description,
                witness_ids=witness_ids,
                location_id=location_id,
                game_time=game_time,
            )
        return self._create_broadcast_memory(
            event_description=event_description,
            witness_ids=witness_ids,
            scope=scope,
            location_id=location_id,
            game_time=game_time,
        )

    def _create_local_memory(
        self,
        event_description: str,
        witness_ids: list[UUID],
        location_id: UUID | None,
        game_time: float,
    ) -> MemoryEventResult:
        personal_ids = [
            self._attach_personal_node(witness_id, event_description, location_id, game_time)
            for witness_id in witness_ids
        ]
        canonical_id = personal_ids[0] if personal_ids else None
        return MemoryEventResult(canonical_id=canonical_id, all_ids=tuple(personal_ids))

    def _create_broadcast_memory(
        self,
        event_description: str,
        witness_ids: list[UUID],
        scope: KnowledgeScope,
        location_id: UUID | None,
        game_time: float,
    ) -> MemoryEventResult:
        broadcast_id = self._graph.add_node(
            KnowledgeNode(
                text=event_description,
                scope=scope,
                source=KnowledgeSource.FACT if scope >= KnowledgeScope.COUNTRY else KnowledgeSource.RUMOR,
                canon=CanonSource.SESSION,
                location_id=location_id,
                timestamp=game_time,
            )
        )
        personal_ids = [
            self._attach_personal_node(witness_id, event_description, location_id, game_time)
            for witness_id in witness_ids
        ]
        return MemoryEventResult(canonical_id=broadcast_id, all_ids=(broadcast_id, *personal_ids))

    def _attach_personal_node(
        self,
        witness_id: UUID,
        event_description: str,
        location_id: UUID | None,
        game_time: float,
    ) -> UUID:
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
        return node_id

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
