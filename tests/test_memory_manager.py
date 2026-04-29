"""Tests for knowledge.memory — MemoryManager.summarize_interaction / create_memory_from_event."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from knowledge.query import KnowledgeQueryEngine
from llm.message import LLMResponse

pytestmark = [
    allure.epic("Memory & Persistence"),
    allure.feature("Memory manager"),
]

_SUMMARY_TEXT = "The merchant now trusts the traveller and shared a rumour."
_EVENT_DESCRIPTION = "A ceremonial explosion rocked the agora."
_LOCATION_ID = "loc-agora"


def _make_manager() -> tuple[MemoryManager, KnowledgeGraph, AsyncMock]:
    graph = KnowledgeGraph()
    llm = AsyncMock()
    llm.send_message = AsyncMock(
        return_value=LLMResponse(body=_SUMMARY_TEXT, model="stub", usage={}),
    )
    return MemoryManager(graph=graph, llm_client=llm), graph, llm


def _seed_npc_node(graph: KnowledgeGraph) -> str:
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
    await manager.summarize_interactions_batch([("unknown-npc-uuid", "whatever")])
    nodes = graph.all_nodes()
    assert len(nodes) == 1
    assert graph.get_edges_from("unknown-npc-uuid") == []


@allure.story("summarize_interactions_batch")
@allure.title("summarize_interactions_batch creates a WITNESSED edge that is queryable via get_memories_about")
@pytest.mark.asyncio
async def test_summarize_batch_creates_witnessed_edge_and_is_queryable() -> None:
    """Register an NPC via register_actor_node, summarise an interaction, then query it back."""
    manager, graph, _ = _make_manager()
    npc_id = "npc-marcus"
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
    witness_ids = ["w1", "w2"]

    created = await manager.create_memory_from_event(
        event_description=_EVENT_DESCRIPTION,
        witness_ids=witness_ids,
        scope=KnowledgeScope.LOCAL,
        location_id=_LOCATION_ID,
    )

    assert len(created) == 2
    for witness_id, node_id in zip(witness_ids, created):
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
@allure.title("create_memory_from_event at CITY scope creates one RUMOR node plus per-witness personal nodes")
@pytest.mark.asyncio
async def test_create_memory_city_scope_produces_rumor_plus_personal() -> None:
    """CITY scope: first node is a CITY RUMOR, followed by per-witness personal copies."""
    manager, graph, _ = _make_manager()
    witness_ids = ["w1", "w2"]

    created = await manager.create_memory_from_event(
        event_description=_EVENT_DESCRIPTION,
        witness_ids=witness_ids,
        scope=KnowledgeScope.CITY,
        location_id=_LOCATION_ID,
    )

    assert len(created) == 3
    rumor_node = graph.get_node(created[0])
    assert rumor_node is not None
    assert rumor_node.scope == KnowledgeScope.CITY
    assert rumor_node.source == KnowledgeSource.RUMOR
    assert rumor_node.canon == CanonSource.SESSION
    assert rumor_node.location_id == _LOCATION_ID
    # The remaining two are personal per-witness
    for witness_id, personal_id in zip(witness_ids, created[1:]):
        personal = graph.get_node(personal_id)
        assert personal is not None
        assert personal.source == KnowledgeSource.PERSONAL_EXPERIENCE
        assert personal.scope == KnowledgeScope.LOCAL
        assert personal.canon == CanonSource.SESSION
        target_ids = [tgt for tgt, _ in graph.get_edges_from(witness_id)]
        assert personal_id in target_ids


@allure.story("create_memory_from_event")
@allure.title("create_memory_from_event at WORLD scope marks the broadcast node as a FACT")
@pytest.mark.asyncio
async def test_create_memory_world_scope_uses_fact_source() -> None:
    """WORLD scope: the scope-wide node uses KnowledgeSource.FACT, not RUMOR."""
    manager, graph, _ = _make_manager()
    created = await manager.create_memory_from_event(
        event_description=_EVENT_DESCRIPTION,
        witness_ids=["w1"],
        scope=KnowledgeScope.WORLD,
        location_id=_LOCATION_ID,
    )
    fact_node = graph.get_node(created[0])
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
    created = await manager.create_memory_from_event(
        event_description=_EVENT_DESCRIPTION,
        witness_ids=["w1", "w2"],
        scope=KnowledgeScope.REGION,
        location_id=_LOCATION_ID,
    )
    assert len(created) == 3
    for node_id in created:
        node = graph.get_node(node_id)
        assert node is not None
        assert node.location_id == _LOCATION_ID
