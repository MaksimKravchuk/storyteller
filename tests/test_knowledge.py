"""Tests for the knowledge subsystem: node, graph, query engine."""

from __future__ import annotations

import allure
import pytest

from knowledge.graph import KnowledgeGraph
from knowledge.graph_queries import (
    get_related,
    query_by_location,
    query_by_scope,
    query_by_tags,
)
from knowledge import graph_serialization
from knowledge.node import EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource
from knowledge.query import KnowledgeFilter, KnowledgeQueryEngine
from models.character import Character

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POLITICS = "politics"
_CONFIDENCE = 0.6


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
    @allure.title("A KnowledgeNode defaults to LOCAL scope, FACT source, zero requirements, and no tags")
    def test_defaults(self):
        node = KnowledgeNode(text="Test fact")
        assert node.scope == KnowledgeScope.LOCAL
        assert node.source == KnowledgeSource.FACT
        assert node.required_education == 0
        assert node.required_social_status == 0
        assert node.tags == []

    @allure.story("Node defaults")
    @allure.title("A KnowledgeNode defaults to full confidence 1.0 and gets a UUID string assigned")
    def test_default_confidence_and_uuid(self):
        node = KnowledgeNode(text="Test fact")
        assert node.confidence == pytest.approx(1.0)
        assert isinstance(node.uuid, str)

    @allure.story("Node defaults")
    @allure.title("A KnowledgeNode accepts custom scope, source, education, tags, and confidence on init")
    def test_custom_fields(self):
        node = KnowledgeNode(
            text="Secret",
            scope=KnowledgeScope.COUNTRY,
            source=KnowledgeSource.RUMOR,
            required_education=5,
            tags=[_POLITICS],
            confidence=_CONFIDENCE,
        )
        assert node.scope == KnowledgeScope.COUNTRY
        assert node.source == KnowledgeSource.RUMOR
        assert node.required_education == 5
        assert node.tags == [_POLITICS]
        assert node.confidence == pytest.approx(_CONFIDENCE)


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
    @allure.title("Adding a RELATED_TO edge between two nodes increments the edge count to 1")
    def test_add_edge_and_edge_count(self, empty_graph):
        n1 = KnowledgeNode(text="A")
        n2 = KnowledgeNode(text="B")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        empty_graph.add_edge(n1.uuid, n2.uuid, EdgeType.RELATED_TO)
        assert graph_serialization.edge_count(empty_graph) == 1

    @allure.story("Edge CRUD")
    @allure.title("get_edges_from returns (target_uuid, edge_type) tuples for all outgoing edges of a node")
    def test_get_edges_from(self, empty_graph):
        n1 = KnowledgeNode(text="A")
        n2 = KnowledgeNode(text="B")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        empty_graph.add_edge(n1.uuid, n2.uuid, EdgeType.KNOWS_ABOUT)
        edges = empty_graph.get_edges_from(n1.uuid)
        assert len(edges) == 1
        target_id, edge_type = edges[0]
        assert target_id == n2.uuid
        assert edge_type == EdgeType.KNOWS_ABOUT

    @allure.story("Edge CRUD")
    @allure.title("get_edges_from returns an empty list for a node id that does not exist in the graph")
    def test_get_edges_from_nonexistent_returns_empty(self, empty_graph):
        assert empty_graph.get_edges_from("ghost") == []

    @allure.story("Edge CRUD")
    @allure.title("get_related does a BFS walk and returns both direct and transitive neighbors within depth")
    def test_get_related_bfs(self, empty_graph):
        nodes = [KnowledgeNode(text=label) for label in ("Root", "Child", "Grandchild")]
        for node in nodes:
            empty_graph.add_node(node)
        empty_graph.add_edge(nodes[0].uuid, nodes[1].uuid, EdgeType.RELATED_TO)
        empty_graph.add_edge(nodes[1].uuid, nodes[2].uuid, EdgeType.RELATED_TO)
        related = get_related(empty_graph, nodes[0].uuid, depth=2)
        related_uuids = {rel_node.uuid for rel_node in related}
        assert nodes[1].uuid in related_uuids
        assert nodes[2].uuid in related_uuids

    @allure.story("Edge CRUD")
    @allure.title("get_related returns an empty list when the starting node does not exist in the graph")
    def test_get_related_unknown_node_returns_empty(self, empty_graph):
        assert get_related(empty_graph, "ghost") == []


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestKnowledgeGraphQueries:
    @allure.story("Query filtering")
    @allure.title("query_by_scope with max_scope CITY excludes all nodes whose scope is WORLD")
    def test_query_by_scope(self, populated_graph):
        # Only LOCAL and CITY nodes should come back when max_scope is CITY
        matching_nodes = query_by_scope(populated_graph, KnowledgeScope.CITY)
        scopes = {node.scope for node in matching_nodes}
        assert KnowledgeScope.WORLD not in scopes

    @allure.story("Query filtering")
    @allure.title("query_by_tags returns only the nodes whose tag list contains the requested tag")
    def test_query_by_tags_match(self, populated_graph):
        matching_nodes = query_by_tags(populated_graph, ["politics"])
        assert len(matching_nodes) == 1
        assert matching_nodes[0].tags == ["politics"]

    @allure.story("Query filtering")
    @allure.title("query_by_tags returns an empty list when no node carries the requested tag")
    def test_query_by_tags_no_match(self, populated_graph):
        matching_nodes = query_by_tags(populated_graph, ["nonexistent"])
        assert matching_nodes == []

    @allure.story("Query filtering")
    @allure.title("query_by_location returns only the nodes whose location_id matches the query")
    def test_query_by_location(self, empty_graph):
        loc_id = "loc-123"
        n1 = KnowledgeNode(text="Here", location_id=loc_id)
        n2 = KnowledgeNode(text="There", location_id="loc-999")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        matching_nodes = query_by_location(empty_graph, loc_id)
        assert len(matching_nodes) == 1
        assert matching_nodes[0].uuid == n1.uuid

    @allure.story("Serialization")
    @allure.title("Serializing a populated graph to a dict and back preserves the total node count")
    def test_serialise_round_trip(self, populated_graph):
        graph_dict = graph_serialization.to_dict(populated_graph)
        restored = graph_serialization.from_dict(graph_dict)
        assert graph_serialization.node_count(restored) == graph_serialization.node_count(populated_graph)


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

    @allure.story("Query engine filters")
    @allure.title("A KnowledgeFilter restricted to FACT source excludes nodes with any other source type")
    def test_query_filters_by_source(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        filt = KnowledgeFilter(sources=[KnowledgeSource.FACT])
        matching_nodes = engine.query(filt)
        assert all(node.source == KnowledgeSource.FACT for node in matching_nodes)

    @allure.story("Query engine filters")
    @allure.title("A KnowledgeFilter with tags=['trade'] returns only the single node tagged 'trade'")
    def test_query_filters_by_tag(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        filt = KnowledgeFilter(tags=["trade"])
        matching_nodes = engine.query(filt)
        assert len(matching_nodes) == 1
        assert "trade" in matching_nodes[0].tags


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestQueryEngineNpcContext:
    @allure.story("NPC context building")
    @allure.title("build_npc_filter maps the Character's knowledge_scope, education, and social_status into the filter")
    def test_build_npc_filter_maps_scope(self):
        npc = Character(
            name="Scholar",
            knowledge_scope="region",
            attributes={"education": 6, "social_status": 4},
        )
        graph = KnowledgeGraph()
        engine = KnowledgeQueryEngine(graph)
        filt = engine.build_npc_filter(npc)
        assert filt.max_scope == KnowledgeScope.REGION
        assert filt.max_education_required == 6
        assert filt.max_social_status_required == 4

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

    @allure.story("NPC context building")
    @allure.title(
        "Passing topic_tags=['trade'] to get_context_for_npc keeps trade facts and drops unrelated conspiracy facts"
    )
    def test_get_context_topic_tag_filters(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        npc = Character(
            name="Trader",
            knowledge_scope="world",
            attributes={"education": 10, "social_status": 10},
        )
        ctx = engine.get_context_for_npc(npc, topic_tags=["trade"])
        assert "silks" in ctx
        assert "conspiracy" not in ctx.lower()
