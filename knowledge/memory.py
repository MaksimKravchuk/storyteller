"""Memory manager — creates knowledge nodes from interactions and events."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from models.game_state import INITIAL_GAME_CLOCK, PlayerState

from knowledge import charge as charge_presets, memory_dedup, node as _node, salience as salience_presets
from knowledge.graph import KnowledgeGraph
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
    shared ``PERSONAL_EXPERIENCE`` node for LOCAL, and ``None`` only
    when no nodes were created. ``all_ids`` carries every created
    node id in creation order:

    * LOCAL with witnesses: ``(shared_personal_id,)``
    * LOCAL with no witnesses: ``()``
    * non-LOCAL with witnesses: ``(broadcast_id, shared_personal_id)``
    * non-LOCAL with no witnesses: ``(broadcast_id,)`` — the wider
      rumor/fact still goes in even when nobody saw it first-hand.
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
    ``tags`` are concept identifiers (e.g. ``light_without_flame``,
    ``image_capture``) that let downstream queries find every memory
    referencing the same abstract idea; without them the field on
    :class:`knowledge.node.KnowledgeNode` was silently dropped at
    every event-creation site.
    """

    event_description: str
    witness_ids: list[UUID]
    scope: _node.KnowledgeScope
    location_id: UUID | None = None
    game_time: float = INITIAL_GAME_CLOCK
    salience: float = salience_presets.DEFAULT
    slots: MemorySlots = EMPTY_SLOTS
    subject_id: UUID | None = None
    tags: list[str] = field(default_factory=list)
    valence: float = charge_presets.NEUTRAL.base_valence
    charge_intensity: float = charge_presets.NEUTRAL.base_intensity
    charge_category: str = charge_presets.NEUTRAL.category


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
        (typically ``player.uuid``). Dialogue summaries carry neutral
        emotional charge — felt charge is stamped on event memories
        (combat, retaliation) via :class:`MemoryEvent`, not chit-chat.
        """
        if not pairs:
            return
        splits = [_split_pair(pair) for pair in pairs]
        coros = [self._summarize_one(split, game_time, location_id, salience, subject_id) for split in splits]
        # Best-effort per NPC: one NPC's summariser failure (LLM timeout
        # / rate-limit / parse error) must not cancel its siblings. This
        # batch feeds scene-end consolidation, after which the caller
        # wipes the action log — an all-or-nothing gather would let one
        # NPC's failure permanently erase every present NPC's scene
        # memory. ``CancelledError`` still propagates so cooperative
        # cancellation is not turned into a log line.
        outcomes = await asyncio.gather(*coros, return_exceptions=True)
        for split, outcome in zip(splits, outcomes):
            if isinstance(outcome, asyncio.CancelledError):
                raise outcome
            if isinstance(outcome, BaseException):
                logger.opt(exception=outcome).error("Per-NPC interaction summary failed (npc={})", split[0])

    async def create_memory_from_event(self, event: MemoryEvent) -> MemoryEventResult:
        """Create memory nodes for all witnesses of an event.

        Scope determines how the memory propagates:
          - LOCAL: only witnesses get PERSONAL_EXPERIENCE
          - CITY/REGION: becomes RUMOR accessible in that area
          - WORLD: becomes FACT accessible broadly

        Co-witnesses share one canonical ``PERSONAL_EXPERIENCE`` node
        with N ``WITNESSED`` edges instead of N near-duplicate nodes,
        so a 10-NPC scene grows by 1 node and 10 edges. ``event.slots``
        is copied onto the shared personal node and the broadcast node
        so a downstream dedup or contradiction-detection pass can
        match on the structured fields instead of re-parsing the free
        text.
        """
        if event.scope == _node.KnowledgeScope.LOCAL:
            return self._create_local_memory(event)
        return self._create_broadcast_memory(event)

    def _create_local_memory(self, event: MemoryEvent) -> MemoryEventResult:
        """LOCAL-scope path: one shared PERSONAL_EXPERIENCE node + N WITNESSED edges."""
        if not event.witness_ids:
            return MemoryEventResult(canonical_id=None)
        personal_id = self._add_shared_personal_node(event)
        return MemoryEventResult(canonical_id=personal_id, all_ids=(personal_id,))

    def _create_broadcast_memory(self, event: MemoryEvent) -> MemoryEventResult:
        """CITY+ scope path: one broadcast node + one shared per-witness personal copy."""
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
                tags=list(event.tags),
                **slot_fields,
            ),
        )
        if not event.witness_ids:
            return MemoryEventResult(canonical_id=broadcast_id, all_ids=(broadcast_id,))
        personal_id = self._add_shared_personal_node(event)
        return MemoryEventResult(canonical_id=broadcast_id, all_ids=(broadcast_id, personal_id))

    def _add_shared_personal_node(self, event: MemoryEvent) -> UUID:
        """Create one ``PERSONAL_EXPERIENCE`` node and link every witness via ``WITNESSED``.

        The shared-node shape keeps memory creation cost
        ``O(witnesses)`` in edges instead of nodes — a 10-NPC scene
        produces one node and ten edges, not ten near-duplicate nodes.
        Per-witness state (e.g. departure-propagation idempotency)
        lives on the WITNESSED edge so the canonical node stays
        immutable across co-witnesses.
        """
        node_id = self._graph.add_node(
            _node.KnowledgeNode(
                text=event.event_description,
                scope=_node.KnowledgeScope.LOCAL,
                source=_node.KnowledgeSource.PERSONAL_EXPERIENCE,
                canon=_node.CanonSource.SESSION,
                location_id=event.location_id,
                timestamp=event.game_time,
                salience=event.salience,
                valence=event.valence,
                charge_intensity=event.charge_intensity,
                charge_category=event.charge_category,
                subject_id=event.subject_id,
                tags=list(event.tags),
                **slot_kwargs(event.slots),
            ),
        )
        for witness_id in event.witness_ids:
            if witness_id not in self._graph.digraph:
                logger.error(
                    "WITNESSED edge for unregistered witness {} on memory {}; "
                    "auto-creating a phantom actor node (graph pollution) — "
                    "NPC registration is out of sync",
                    witness_id,
                    node_id,
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
        if not summary_text or memory_dedup.has_near_duplicate_memory(self._graph, npc_id, summary_text):
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
        else:
            logger.error(
                "Summary node {} created for unregistered NPC {}; WITNESSED edge dropped, "
                "NPC has no scene memory — NPC registration is out of sync",
                node_id,
                npc_id,
            )
