"""Tests for knowledge.memory — MemoryManager.summarize_interaction / create_memory_from_event."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import allure
import pytest

from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryEventResult, MemoryManager, record_player_learned_fact
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from knowledge.query import KnowledgeQueryEngine
from llm.message import LLMResponse
from models.game_state import PlayerState
from tests._uuid_helpers import make_uuid

pytestmark = [
    allure.epic("Memory & Persistence"),
    allure.feature("Memory manager"),
]

_SUMMARY_TEXT = "The merchant now trusts the traveller and shared a rumour."
_EVENT_DESCRIPTION = "A ceremonial explosion rocked the agora."
_LOCATION_ID = make_uuid("loc-agora")
_W1 = make_uuid("w1")
_W2 = make_uuid("w2")
_UNKNOWN_NPC = make_uuid("unknown-npc-uuid")
_MARCUS = make_uuid("npc-marcus")


def _make_manager() -> tuple[MemoryManager, KnowledgeGraph, AsyncMock]:
    graph = KnowledgeGraph()
    llm = AsyncMock()
    llm.send_message = AsyncMock(
        return_value=LLMResponse(body=_SUMMARY_TEXT, model="stub", usage={}),
    )
    return MemoryManager(graph=graph, llm_client=llm), graph, llm


def _seed_npc_node(graph: KnowledgeGraph) -> UUID:
    npc_node = KnowledgeNode(
        text="Marcus the legionary",
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.FACT,
    )
    return graph.add_node(npc_node)


@allure.story("summarize_interactions_batch")
@allure.title("summarize_interactions_batch creates a memory node and links it to an existing NPC with WITNESSED")
@pytest.mark.asyncio
async def test_summarize_batch_links_to_existing_npc() -> None:
    """When the NPC is already in the graph, a WITNESSED edge is added from NPC to the memory."""
    manager, graph, llm = _make_manager()
    npc_id = _seed_npc_node(graph)

    await manager.summarize_interactions_batch([(npc_id, "player: hi\nnpc: hello")])

    memory_nodes = [n for n in graph.all_nodes() if n.source == KnowledgeSource.PERSONAL_EXPERIENCE]
    assert len(memory_nodes) == 1
    node = memory_nodes[0]
    assert node.text == _SUMMARY_TEXT
    assert node.scope == KnowledgeScope.LOCAL
    assert node.source == KnowledgeSource.PERSONAL_EXPERIENCE
    assert node.canon == CanonSource.SESSION
    edges = graph.get_edges_from(npc_id)
    assert len(edges) == 1
    target_id, edge_type = edges[0]
    assert target_id == node.uuid
    assert edge_type == EdgeType.WITNESSED
    llm.send_message.assert_awaited_once()


@allure.story("summarize_interactions_batch")
@allure.title("summarize_interactions_batch still creates a node when the npc_id is missing from the graph")
@pytest.mark.asyncio
async def test_summarize_batch_no_edge_when_npc_missing() -> None:
    """With an unknown npc_id, the node is added but no edge is created."""
    manager, graph, _ = _make_manager()
    await manager.summarize_interactions_batch([(_UNKNOWN_NPC, "whatever")])
    nodes = graph.all_nodes()
    assert len(nodes) == 1
    assert graph.get_edges_from(_UNKNOWN_NPC) == []


@allure.story("summarize_interactions_batch")
@allure.title("summarize_interactions_batch creates a WITNESSED edge that is queryable via get_memories_about")
@pytest.mark.asyncio
async def test_summarize_batch_creates_witnessed_edge_and_is_queryable() -> None:
    """Register an NPC via register_actor_node, summarise an interaction, then query it back."""
    manager, graph, _ = _make_manager()
    npc_id = _MARCUS
    graph.register_actor_node(npc_id, label="Marcus (legionary)")

    await manager.summarize_interactions_batch([(npc_id, "Player: greetings\nMarcus: hail")], game_time=3.0)

    edges = graph.get_edges_from(npc_id)
    assert len(edges) == 1
    node_id, edge_type = edges[0]
    assert edge_type == EdgeType.WITNESSED

    engine = KnowledgeQueryEngine(graph)
    memories = engine.get_memories_about(npc_id)
    assert len(memories) == 1
    assert memories[0].uuid == node_id
    assert memories[0].text == _SUMMARY_TEXT


@allure.story("create_memory_from_event")
@allure.title("create_memory_from_event at LOCAL scope creates per-witness PERSONAL_EXPERIENCE nodes")
@pytest.mark.asyncio
async def test_create_memory_local_scope_personal_per_witness() -> None:
    """LOCAL scope: one PERSONAL_EXPERIENCE node per witness, each WITNESSED-linked."""
    manager, graph, _ = _make_manager()
    witness_ids = [_W1, _W2]

    result = await manager.create_memory_from_event(
        event_description=_EVENT_DESCRIPTION,
        witness_ids=witness_ids,
        scope=KnowledgeScope.LOCAL,
        location_id=_LOCATION_ID,
    )

    assert len(result.all_ids) == 2
    assert result.canonical_id is not None
    assert result.canonical_id in result.all_ids
    for witness_id, node_id in zip(witness_ids, result.all_ids):
        node = graph.get_node(node_id)
        assert node is not None
        assert node.source == KnowledgeSource.PERSONAL_EXPERIENCE
        assert node.scope == KnowledgeScope.LOCAL
        assert node.canon == CanonSource.SESSION
        assert node.location_id == _LOCATION_ID
        edges = graph.get_edges_from(witness_id)
        # The witness wasn't seeded in graph, but edge should still exist with WITNESSED type
        target_ids = [tgt for tgt, _ in edges]
        assert node_id in target_ids


@allure.story("create_memory_from_event")
@allure.title(
    "create_memory_from_event at LOCAL scope with no witnesses returns an empty result with canonical_id=None"
)
@pytest.mark.asyncio
async def test_create_memory_local_scope_no_witnesses_returns_empty_result() -> None:
    """Empty witness list returns no node ids and no canonical id."""
    manager, _graph, _ = _make_manager()

    result = await manager.create_memory_from_event(
        event_description=_EVENT_DESCRIPTION,
        witness_ids=[],
        scope=KnowledgeScope.LOCAL,
        location_id=_LOCATION_ID,
    )

    assert result.canonical_id is None
    assert result.all_ids == ()


@allure.story("create_memory_from_event")
@allure.title("create_memory_from_event at CITY scope marks the broadcast RUMOR as canonical")
@pytest.mark.asyncio
async def test_create_memory_city_scope_canonical_is_broadcast_rumor() -> None:
    """CITY scope: canonical_id resolves to the broadcast RUMOR node."""
    manager, graph, _ = _make_manager()
    witness_ids = [_W1, _W2]

    result = await manager.create_memory_from_event(
        event_description=_EVENT_DESCRIPTION,
        witness_ids=witness_ids,
        scope=KnowledgeScope.CITY,
        location_id=_LOCATION_ID,
    )

    assert len(result.all_ids) == 3
    assert result.canonical_id is not None
    canonical_node = graph.get_node(result.canonical_id)
    assert canonical_node is not None
    assert canonical_node.scope == KnowledgeScope.CITY
    assert canonical_node.source == KnowledgeSource.RUMOR
    assert canonical_node.canon == CanonSource.SESSION
    assert canonical_node.location_id == _LOCATION_ID
    personal_ids = [node_id for node_id in result.all_ids if node_id != result.canonical_id]
    assert len(personal_ids) == len(witness_ids)
    for witness_id, personal_id in zip(witness_ids, personal_ids):
        personal = graph.get_node(personal_id)
        assert personal is not None
        assert personal.source == KnowledgeSource.PERSONAL_EXPERIENCE
        assert personal.scope == KnowledgeScope.LOCAL
        assert personal.canon == CanonSource.SESSION
        target_ids = [tgt for tgt, _ in graph.get_edges_from(witness_id)]
        assert personal_id in target_ids


@allure.story("create_memory_from_event")
@allure.title("create_memory_from_event at WORLD scope marks the broadcast canonical node as a FACT")
@pytest.mark.asyncio
async def test_create_memory_world_scope_uses_fact_source() -> None:
    """WORLD scope: the canonical broadcast node uses KnowledgeSource.FACT, not RUMOR."""
    manager, graph, _ = _make_manager()
    result = await manager.create_memory_from_event(
        event_description=_EVENT_DESCRIPTION,
        witness_ids=[_W1],
        scope=KnowledgeScope.WORLD,
        location_id=_LOCATION_ID,
    )
    assert result.canonical_id is not None
    fact_node = graph.get_node(result.canonical_id)
    assert fact_node is not None
    assert fact_node.scope == KnowledgeScope.WORLD
    assert fact_node.source == KnowledgeSource.FACT
    assert fact_node.canon == CanonSource.SESSION


@allure.story("create_memory_from_event")
@allure.title("create_memory_from_event propagates location_id to every node it creates")
@pytest.mark.asyncio
async def test_create_memory_propagates_location_id() -> None:
    """Every created node — fact and personal — must carry the supplied location_id."""
    manager, graph, _ = _make_manager()
    result = await manager.create_memory_from_event(
        event_description=_EVENT_DESCRIPTION,
        witness_ids=[_W1, _W2],
        scope=KnowledgeScope.REGION,
        location_id=_LOCATION_ID,
    )
    assert len(result.all_ids) == 3
    for node_id in result.all_ids:
        node = graph.get_node(node_id)
        assert node is not None
        assert node.location_id == _LOCATION_ID


@allure.story("record_player_learned_fact")
@allure.title("record_player_learned_fact stores the explicit canonical UUID even when it is not all_ids[0]")
def test_record_player_learned_fact_uses_canonical_not_first() -> None:
    """The canonical UUID is recorded regardless of its position inside ``all_ids``."""
    player = PlayerState(name="Player")
    canonical = make_uuid("canonical-broadcast")
    other = make_uuid("personal-witness")
    result = MemoryEventResult(canonical_id=canonical, all_ids=(other, canonical))

    record_player_learned_fact(player, result.canonical_id)

    assert player.learned_facts == {canonical}


@allure.story("record_player_learned_fact")
@allure.title("record_player_learned_fact is a no-op when canonical_id is None")
def test_record_player_learned_fact_noop_on_none() -> None:
    """``canonical_id=None`` must not pollute ``learned_facts``."""
    player = PlayerState(name="Player")
    record_player_learned_fact(player, None)
    assert player.learned_facts == set()
