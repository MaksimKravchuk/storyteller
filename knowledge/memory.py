"""Memory manager — creates knowledge nodes from interactions and events."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from models.game_state import INITIAL_GAME_CLOCK, PlayerState

from knowledge import node as _node, salience as salience_presets
from knowledge.graph import KnowledgeGraph
from knowledge.memory_dedup import has_near_duplicate_memory
from knowledge.memory_slots import EMPTY_SLOTS, MemorySlots, slot_kwargs

if TYPE_CHECKING:
    from llm.base_client import BaseLLMClient

_SUMMARY_MAX_TOKENS = 200
_SUMMARISER_SYSTEM_PROMPT = (
    "You are a memory summariser for a text adventure game. Output only the summary, nothing else."
)
_SUMMARISER_USER_PROMPT = (
    "Summarise the following conversation from the NPC's perspective "
    "in 1-2 sentences. Focus on: what did the NPC learn? "
    "What is their impression of the player?\n\n"
)

# A 2-tuple ``(npc_id, transcript)`` carries no slots; a 3-tuple
# ``(npc_id, transcript, slots)`` carries explicit subject/object/action
# values. Both forms feed ``summarize_interactions_batch``.
DialoguePair = tuple[UUID, str] | tuple[UUID, str, MemorySlots]


def _split_pair(pair: DialoguePair) -> tuple[UUID, str, MemorySlots]:
    """Normalise a 2- or 3-tuple :data:`DialoguePair` to ``(npc_id, log, slots)``."""
    if len(pair) == 3:
        return pair[0], pair[1], pair[2]
    return pair[0], pair[1], EMPTY_SLOTS


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
    """Add the canonical memory UUID to ``player.learned_facts``, if any.

    Called by witness-broadcast paths that want the Character sidebar
    to render a ``RememberedFact`` for events the player witnessed.
    ``canonical_id=None`` is a no-op so callers can pass
    ``MemoryEventResult.canonical_id`` unconditionally.
    """
    if canonical_id is not None:
        player.learned_facts.add(canonical_id)


@dataclass(frozen=True)
class MemoryEvent:
    """Inputs for :meth:`MemoryManager.create_memory_from_event`.

    ``salience`` defaults to the neutral preset; combat / overheard /
    event sites pick a tuned value from :mod:`knowledge.salience`.
    ``slots`` carries the optional structured
    subject/object/action/outcome quadruple (see
    :class:`knowledge.memory_slots.MemorySlots`). ``subject_id`` is the
    canonical UUID of the entity the resulting nodes are *about* —
    distinct from ``slots.subject`` (free-text name) — so a later
    :meth:`KnowledgeGraph.resolve_subject_identity` lookup can find
    every memory tagged with the same person across encounters.
    """

    event_description: str
    witness_ids: list[UUID]
    scope: _node.KnowledgeScope
    location_id: UUID | None = None
    game_time: float = INITIAL_GAME_CLOCK
    salience: float = salience_presets.DEFAULT
    slots: MemorySlots = EMPTY_SLOTS
    subject_id: UUID | None = None


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
        pairs: list[DialoguePair],
        game_time: float = INITIAL_GAME_CLOCK,
        location_id: UUID | None = None,
        salience: float = salience_presets.ROUTINE_DIALOGUE,
        subject_id: UUID | None = None,
    ) -> None:
        """Summarise many interactions concurrently into memory nodes.

        Each ``pair`` is ``(npc_id, interaction_log)`` or
        ``(npc_id, interaction_log, slots)``. ``salience`` is the
        importance score stamped on every produced memory; ``subject_id``
        is the canonical entity all summaries on this turn are about
        (typically ``player.uuid``).
        """
        if not pairs:
            return
        coros = [
            self._summarize_one(_split_pair(pair), game_time, location_id, salience, subject_id) for pair in pairs
        ]
        await asyncio.gather(*coros)

    async def create_memory_from_event(self, event: MemoryEvent) -> MemoryEventResult:
        """Create memory nodes for all witnesses of an event.

        Scope determines how the memory propagates:
          - LOCAL: only witnesses get PERSONAL_EXPERIENCE
          - CITY/REGION: becomes RUMOR accessible in that area
          - WORLD: becomes FACT accessible broadly

        ``event.slots`` is copied onto every per-witness ``KnowledgeNode``
        as well as the broadcast node so a downstream dedup or
        contradiction-detection pass can match on the structured fields
        instead of re-parsing the free text.
        """
        if event.scope == _node.KnowledgeScope.LOCAL:
            return self._create_local_memory(event)
        return self._create_broadcast_memory(event)

    def _create_local_memory(self, event: MemoryEvent) -> MemoryEventResult:
        """LOCAL-scope path: one PERSONAL_EXPERIENCE node per witness."""
        slot_fields = slot_kwargs(event.slots)
        personal_ids = [self._attach_personal_node(event, witness_id, slot_fields) for witness_id in event.witness_ids]
        canonical_id = personal_ids[0] if personal_ids else None
        return MemoryEventResult(canonical_id=canonical_id, all_ids=tuple(personal_ids))

    def _create_broadcast_memory(self, event: MemoryEvent) -> MemoryEventResult:
        """CITY+ scope path: one broadcast node plus per-witness personal copies."""
        slot_fields = slot_kwargs(event.slots)
        broadcast_source = (
            _node.KnowledgeSource.FACT if event.scope >= _node.KnowledgeScope.COUNTRY else _node.KnowledgeSource.RUMOR
        )
        broadcast_id = self._graph.add_node(
            _node.KnowledgeNode(
                text=event.event_description,
                scope=event.scope,
                source=broadcast_source,
                canon=_node.CanonSource.SESSION,
                location_id=event.location_id,
                timestamp=event.game_time,
                salience=event.salience,
                subject_id=event.subject_id,
                **slot_fields,
            ),
        )
        personal_ids = [self._attach_personal_node(event, witness_id, slot_fields) for witness_id in event.witness_ids]
        return MemoryEventResult(canonical_id=broadcast_id, all_ids=(broadcast_id, *personal_ids))

    def _attach_personal_node(self, event: MemoryEvent, witness_id: UUID, slot_fields: dict) -> UUID:
        """Add a LOCAL ``PERSONAL_EXPERIENCE`` node and link it to ``witness_id``."""
        node_id = self._graph.add_node(
            _node.KnowledgeNode(
                text=event.event_description,
                scope=_node.KnowledgeScope.LOCAL,
                source=_node.KnowledgeSource.PERSONAL_EXPERIENCE,
                canon=_node.CanonSource.SESSION,
                location_id=event.location_id,
                timestamp=event.game_time,
                salience=event.salience,
                subject_id=event.subject_id,
                **slot_fields,
            ),
        )
        self._graph.add_edge(witness_id, node_id, _node.EdgeType.WITNESSED)
        return node_id

    async def _summarize_one(
        self,
        pair: tuple[UUID, str, MemorySlots],
        game_time: float,
        location_id: UUID | None,
        salience: float,
        subject_id: UUID | None,
    ) -> None:
        """Summarise a single interaction into a memory node linked to an NPC."""
        from llm.message import Message, Role

        npc_id = pair[0]
        response = await self._llm.send_message(
            messages=[Message(role=Role.USER, body=_SUMMARISER_USER_PROMPT + pair[1])],
            system_prompt=_SUMMARISER_SYSTEM_PROMPT,
            max_tokens=_SUMMARY_MAX_TOKENS,
        )
        summary_text = response.body.strip()
        if not summary_text or has_near_duplicate_memory(self._graph, npc_id, summary_text):
            return
        node_id = self._graph.add_node(
            _node.KnowledgeNode(
                text=summary_text,
                scope=_node.KnowledgeScope.LOCAL,
                source=_node.KnowledgeSource.PERSONAL_EXPERIENCE,
                canon=_node.CanonSource.SESSION,
                location_id=location_id,
                timestamp=game_time,
                salience=salience,
                subject_id=subject_id,
                **slot_kwargs(pair[2]),
            ),
        )
        if npc_id in self._graph.digraph:
            self._graph.add_edge(npc_id, node_id, _node.EdgeType.WITNESSED)
