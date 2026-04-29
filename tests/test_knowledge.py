"""Tests for the knowledge subsystem: node, graph, query engine."""

from __future__ import annotations

import allure

from knowledge.graph import KnowledgeGraph
from knowledge import graph_serialization
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from knowledge.query import KnowledgeFilter, KnowledgeQueryEngine
from models.character import Character

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POLITICS = "politics"


# ---------------------------------------------------------------------------
# KnowledgeScope ordering
# ---------------------------------------------------------------------------


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestKnowledgeScopeOrdering:
    @allure.story("Scope ordering")
    @allure.title("KnowledgeScope.LOCAL is ordered strictly below KnowledgeScope.CITY")
    def test_local_lt_city(self):
        assert KnowledgeScope.LOCAL < KnowledgeScope.CITY

    @allure.story("Scope ordering")
    @allure.title("KnowledgeScope.WORLD is ordered strictly above KnowledgeScope.REGION")
    def test_world_gt_region(self):
        assert KnowledgeScope.WORLD > KnowledgeScope.REGION

    @allure.story("Scope ordering")
    @allure.title("KnowledgeScope comparison operators treat identical scopes as both <= and >=")
    def test_equal_scope(self):
        assert KnowledgeScope.CITY <= KnowledgeScope.CITY
        assert KnowledgeScope.CITY >= KnowledgeScope.CITY

    @allure.story("Scope ordering")
    @allure.title("The full scope ordering runs LOCAL < CITY < REGION < COUNTRY < WORLD")
    def test_full_ordering(self):
        order = [
            KnowledgeScope.LOCAL,
            KnowledgeScope.CITY,
            KnowledgeScope.REGION,
            KnowledgeScope.COUNTRY,
            KnowledgeScope.WORLD,
        ]
        for idx in range(len(order) - 1):
            assert order[idx] < order[idx + 1]


# ---------------------------------------------------------------------------
# KnowledgeNode
# ---------------------------------------------------------------------------


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestKnowledgeNode:
    @allure.story("Node defaults")
    @allure.title("A KnowledgeNode defaults to LOCAL scope, FACT source, zero education, and no tags")
    def test_defaults(self):
        node = KnowledgeNode(text="Test fact")
        assert node.scope == KnowledgeScope.LOCAL
        assert node.source == KnowledgeSource.FACT
        assert node.required_education == 0
        assert node.tags == []

    @allure.story("Node defaults")
    @allure.title("A KnowledgeNode gets a UUID string assigned on init")
    def test_default_uuid(self):
        node = KnowledgeNode(text="Test fact")
        assert isinstance(node.uuid, str)

    @allure.story("Node defaults")
    @allure.title("A KnowledgeNode accepts custom scope, source, education, and tags on init")
    def test_custom_fields(self):
        node = KnowledgeNode(
            text="Secret",
            scope=KnowledgeScope.COUNTRY,
            source=KnowledgeSource.RUMOR,
            required_education=5,
            tags=[_POLITICS],
        )
        assert node.scope == KnowledgeScope.COUNTRY
        assert node.source == KnowledgeSource.RUMOR
        assert node.required_education == 5
        assert node.tags == [_POLITICS]

    @allure.story("Canon source")
    @allure.title("A KnowledgeNode defaults its canon to HISTORICAL")
    def test_default_canon_is_historical(self):
        node = KnowledgeNode(text="Caesar crossed the Rubicon")
        assert node.canon == CanonSource.HISTORICAL

    @allure.story("Canon source")
    @allure.title("A KnowledgeNode accepts an explicit SESSION canon on init")
    def test_custom_canon_session(self):
        node = KnowledgeNode(text="Player slew the duke", canon=CanonSource.SESSION)
        assert node.canon == CanonSource.SESSION


# ---------------------------------------------------------------------------
# KnowledgeGraph
# ---------------------------------------------------------------------------


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestKnowledgeGraphNodes:
    @allure.story("Node CRUD")
    @allure.title("Adding a node to the graph returns its UUID and allows retrieval by that UUID")
    def test_add_and_get_node(self, empty_graph):
        node = KnowledgeNode(text="Fact A")
        uid = empty_graph.add_node(node)
        assert uid == node.uuid
        retrieved = empty_graph.get_node(uid)
        assert retrieved is node

    @allure.story("Node CRUD")
    @allure.title("get_node returns None when the requested UUID is not in the graph")
    def test_get_node_missing_returns_none(self, empty_graph):
        assert empty_graph.get_node("nonexistent") is None

    @allure.story("Node CRUD")
    @allure.title("graph_serialization.node_count correctly reflects how many nodes are in the graph")
    def test_node_count(self, empty_graph):
        assert graph_serialization.node_count(empty_graph) == 0
        empty_graph.add_node(KnowledgeNode(text="A"))
        empty_graph.add_node(KnowledgeNode(text="B"))
        assert graph_serialization.node_count(empty_graph) == 2

    @allure.story("Node CRUD")
    @allure.title("Removing a node drops it from the graph and decrements the node count")
    def test_remove_node(self, empty_graph):
        node = KnowledgeNode(text="Removable")
        empty_graph.add_node(node)
        empty_graph.remove_node(node.uuid)
        assert empty_graph.get_node(node.uuid) is None
        assert graph_serialization.node_count(empty_graph) == 0

    @allure.story("Node CRUD")
    @allure.title("Removing a nonexistent node id is a silent no-op rather than raising")
    def test_remove_nonexistent_node_is_noop(self, empty_graph):
        empty_graph.remove_node("ghost")  # should not raise

    @allure.story("Node CRUD")
    @allure.title("all_nodes returns every node currently in the populated graph fixture")
    def test_all_nodes(self, populated_graph):
        nodes = populated_graph.all_nodes()
        assert len(nodes) == 3


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestKnowledgeGraphEdges:
    @allure.story("Edge CRUD")
    @allure.title("Adding a WITNESSED edge between two nodes increments the edge count to 1")
    def test_add_edge_and_edge_count(self, empty_graph):
        n1 = KnowledgeNode(text="A")
        n2 = KnowledgeNode(text="B")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        empty_graph.add_edge(n1.uuid, n2.uuid, EdgeType.WITNESSED)
        assert graph_serialization.edge_count(empty_graph) == 1

    @allure.story("Edge CRUD")
    @allure.title("get_edges_from returns (target_uuid, edge_type) tuples for all outgoing edges of a node")
    def test_get_edges_from(self, empty_graph):
        n1 = KnowledgeNode(text="A")
        n2 = KnowledgeNode(text="B")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        empty_graph.add_edge(n1.uuid, n2.uuid, EdgeType.TOLD_BY)
        edges = empty_graph.get_edges_from(n1.uuid)
        assert len(edges) == 1
        target_id, edge_type = edges[0]
        assert target_id == n2.uuid
        assert edge_type == EdgeType.TOLD_BY

    @allure.story("Edge CRUD")
    @allure.title("get_edges_from returns an empty list for a node id that does not exist in the graph")
    def test_get_edges_from_nonexistent_returns_empty(self, empty_graph):
        assert empty_graph.get_edges_from("ghost") == []


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestKnowledgeGraphSerialization:
    @allure.story("Serialization")
    @allure.title("Serializing a populated graph to a dict and back preserves the total node count")
    def test_serialise_round_trip(self, populated_graph):
        graph_dict = graph_serialization.to_dict(populated_graph)
        restored = graph_serialization.from_dict(graph_dict)
        assert graph_serialization.node_count(restored) == graph_serialization.node_count(populated_graph)

    @allure.story("Serialization")
    @allure.title("Round-tripping a graph through to_dict/from_dict preserves the canon on each node")
    def test_serialise_round_trip_preserves_canon(self, empty_graph):
        historical = KnowledgeNode(text="Wikipedia fact", canon=CanonSource.HISTORICAL)
        session = KnowledgeNode(text="Player action", canon=CanonSource.SESSION)
        empty_graph.add_node(historical)
        empty_graph.add_node(session)

        restored = graph_serialization.from_dict(graph_serialization.to_dict(empty_graph))
        canons_by_uuid = {node.uuid: node.canon for node in restored.all_nodes()}
        assert canons_by_uuid[historical.uuid] == CanonSource.HISTORICAL
        assert canons_by_uuid[session.uuid] == CanonSource.SESSION


# ---------------------------------------------------------------------------
# KnowledgeQueryEngine
# ---------------------------------------------------------------------------


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestQueryEngineFilters:
    @allure.story("Query engine filters")
    @allure.title("A KnowledgeFilter with WORLD max_scope matches every node in a populated graph")
    def test_query_all_world_scope(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        filt = KnowledgeFilter(max_scope=KnowledgeScope.WORLD)
        matching_nodes = engine.query(filt)
        assert len(matching_nodes) == 3  # all three nodes

    @allure.story("Query engine filters")
    @allure.title("A KnowledgeFilter with max_scope LOCAL returns only nodes whose scope is LOCAL")
    def test_query_filters_by_scope(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        filt = KnowledgeFilter(max_scope=KnowledgeScope.LOCAL)
        matching_nodes = engine.query(filt)
        # Only the LOCAL node should pass
        assert all(node.scope == KnowledgeScope.LOCAL for node in matching_nodes)

    @allure.story("Query engine filters")
    @allure.title("A max_education_required of 3 excludes a scholar-only node that requires education 8")
    def test_query_filters_by_education(self, empty_graph):
        low_node = KnowledgeNode(text="Common knowledge", required_education=0)
        high_node = KnowledgeNode(text="Scholar knowledge", required_education=8)
        empty_graph.add_node(low_node)
        empty_graph.add_node(high_node)
        engine = KnowledgeQueryEngine(empty_graph)
        matched_uuids = {node.uuid for node in engine.query(KnowledgeFilter(max_education_required=3))}
        assert low_node.uuid in matched_uuids
        assert high_node.uuid not in matched_uuids


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestQueryEngineNpcContext:
    @allure.story("NPC context building")
    @allure.title("build_npc_filter maps the Character's knowledge_scope and education into the filter")
    def test_build_npc_filter_maps_scope(self):
        npc = Character(
            name="Scholar",
            knowledge_scope="region",
            attributes={"education": 6},
        )
        graph = KnowledgeGraph()
        engine = KnowledgeQueryEngine(graph)
        filt = engine.build_npc_filter(npc)
        assert filt.max_scope == KnowledgeScope.REGION
        assert filt.max_education_required == 6

    @allure.story("NPC context building")
    @allure.title("An unknown knowledge_scope string on a Character falls back to LOCAL scope in the filter")
    def test_npc_filter_unknown_scope_defaults_local(self):
        npc = Character(name="Mystery", knowledge_scope="galaxy")
        graph = KnowledgeGraph()
        engine = KnowledgeQueryEngine(graph)
        filt = engine.build_npc_filter(npc)
        assert filt.max_scope == KnowledgeScope.LOCAL

    @allure.story("NPC context building")
    @allure.title(
        "get_context_for_npc on an empty graph returns a fallback 'don't have any specific knowledge' message"
    )
    def test_empty_graph_returns_default_message(self, empty_graph):
        engine = KnowledgeQueryEngine(empty_graph)
        npc = Character(name="Joe", knowledge_scope="world")
        ctx = engine.get_context_for_npc(npc)
        assert "don't have any specific knowledge" in ctx

    @allure.story("NPC context building")
    @allure.title("RUMOR-sourced knowledge items are prefixed with '[Rumour]' in the generated NPC context string")
    def test_get_context_prefixes_rumours(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        npc = Character(
            name="Gossip",
            knowledge_scope="world",
            attributes={"education": 10, "social_status": 10},
        )
        ctx = engine.get_context_for_npc(npc)
        assert "[Rumour]" in ctx


def _attach_memory(
    graph: KnowledgeGraph,
    npc_id: str,
    text: str,
    timestamp: float,
) -> KnowledgeNode:
    """Helper: add a PERSONAL_EXPERIENCE node and link it to an NPC via WITNESSED."""
    memory = KnowledgeNode(
        text=text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        timestamp=timestamp,
    )
    memory_id = graph.add_node(memory)
    graph.add_edge(npc_id, memory_id, EdgeType.WITNESSED)
    return memory


@allure.epic("Memory & Persistence")
@allure.feature("Memory query")
class TestQueryEngineGetMemoriesAbout:
    @allure.story("get_memories_about")
    @allure.title("get_memories_about returns an empty list for a graph with no memory edges")
    def test_empty_graph_returns_empty(self, empty_graph):
        empty_graph.register_actor_node("npc-1", label="Guard")
        engine = KnowledgeQueryEngine(empty_graph)
        assert engine.get_memories_about("npc-1") == []

    @allure.story("get_memories_about")
    @allure.title("get_memories_about returns a single PERSONAL_EXPERIENCE node linked to the NPC via WITNESSED")
    def test_single_memory_returned(self, empty_graph):
        empty_graph.register_actor_node("npc-1", label="Guard")
        memory = _attach_memory(empty_graph, "npc-1", "Met a kind traveller", timestamp=1.0)

        engine = KnowledgeQueryEngine(empty_graph)
        memories = engine.get_memories_about("npc-1")

        assert len(memories) == 1
        assert memories[0].uuid == memory.uuid

    @allure.story("get_memories_about")
    @allure.title("get_memories_about caps the result at the requested limit")
    def test_limit_respected(self, empty_graph):
        empty_graph.register_actor_node("npc-1", label="Guard")
        for idx in range(5):
            _attach_memory(empty_graph, "npc-1", f"memory-{idx}", timestamp=float(idx))

        engine = KnowledgeQueryEngine(empty_graph)
        assert len(engine.get_memories_about("npc-1", limit=2)) == 2

    @allure.story("get_memories_about")
    @allure.title("get_memories_about orders memories by timestamp descending (newest first)")
    def test_orders_by_timestamp_descending(self, empty_graph):
        empty_graph.register_actor_node("npc-1", label="Guard")
        _attach_memory(empty_graph, "npc-1", "oldest", timestamp=1.0)
        _attach_memory(empty_graph, "npc-1", "newest", timestamp=3.0)
        _attach_memory(empty_graph, "npc-1", "middle", timestamp=2.0)

        engine = KnowledgeQueryEngine(empty_graph)
        ordered_texts = [mem.text for mem in engine.get_memories_about("npc-1")]
        assert ordered_texts == ["newest", "middle", "oldest"]
