"""Tests for the knowledge subsystem: node, graph, query engine."""

from __future__ import annotations


from knowledge.graph import KnowledgeGraph
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


class TestKnowledgeScopeOrdering:
    def test_local_lt_city(self):
        assert KnowledgeScope.LOCAL < KnowledgeScope.CITY

    def test_world_gt_region(self):
        assert KnowledgeScope.WORLD > KnowledgeScope.REGION

    def test_equal_scope(self):
        assert KnowledgeScope.CITY <= KnowledgeScope.CITY
        assert KnowledgeScope.CITY >= KnowledgeScope.CITY

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


class TestKnowledgeNode:
    def test_defaults(self):
        node = KnowledgeNode(content="Test fact")
        assert node.scope == KnowledgeScope.LOCAL
        assert node.source == KnowledgeSource.FACT
        assert node.required_education == 0
        assert node.required_social_status == 0
        assert node.tags == []
        assert node.confidence == 1.0  # noqa: WPS459
        assert isinstance(node.uuid, str)

    def test_custom_fields(self):
        node = KnowledgeNode(
            content="Secret",
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
        assert node.confidence == _CONFIDENCE  # noqa: WPS459


# ---------------------------------------------------------------------------
# KnowledgeGraph
# ---------------------------------------------------------------------------


class TestKnowledgeGraph:
    def test_add_and_get_node(self, empty_graph):
        node = KnowledgeNode(content="Fact A")
        uid = empty_graph.add_node(node)
        assert uid == node.uuid
        retrieved = empty_graph.get_node(uid)
        assert retrieved is node

    def test_get_node_missing_returns_none(self, empty_graph):
        assert empty_graph.get_node("nonexistent") is None

    def test_node_count(self, empty_graph):
        assert empty_graph.node_count == 0
        empty_graph.add_node(KnowledgeNode(content="A"))
        empty_graph.add_node(KnowledgeNode(content="B"))
        assert empty_graph.node_count == 2

    def test_remove_node(self, empty_graph):
        node = KnowledgeNode(content="Removable")
        empty_graph.add_node(node)
        empty_graph.remove_node(node.uuid)
        assert empty_graph.get_node(node.uuid) is None
        assert empty_graph.node_count == 0

    def test_remove_nonexistent_node_is_noop(self, empty_graph):
        empty_graph.remove_node("ghost")  # should not raise

    def test_all_nodes(self, populated_graph):
        nodes = populated_graph.all_nodes()
        assert len(nodes) == 3

    def test_add_edge_and_edge_count(self, empty_graph):
        n1 = KnowledgeNode(content="A")
        n2 = KnowledgeNode(content="B")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        empty_graph.add_edge(n1.uuid, n2.uuid, EdgeType.RELATED_TO)
        assert empty_graph.edge_count == 1

    def test_get_edges_from(self, empty_graph):
        n1 = KnowledgeNode(content="A")
        n2 = KnowledgeNode(content="B")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        empty_graph.add_edge(n1.uuid, n2.uuid, EdgeType.KNOWS_ABOUT)
        edges = empty_graph.get_edges_from(n1.uuid)
        assert len(edges) == 1
        target_id, edge_type = edges[0]
        assert target_id == n2.uuid
        assert edge_type == EdgeType.KNOWS_ABOUT

    def test_get_edges_from_nonexistent_returns_empty(self, empty_graph):
        assert empty_graph.get_edges_from("ghost") == []

    def test_query_by_scope(self, populated_graph):
        # Only LOCAL and CITY nodes should come back when max_scope is CITY
        matching_nodes = populated_graph.query_by_scope(KnowledgeScope.CITY)
        scopes = {node.scope for node in matching_nodes}
        assert KnowledgeScope.WORLD not in scopes

    def test_query_by_tags_match(self, populated_graph):
        matching_nodes = populated_graph.query_by_tags(["politics"])
        assert len(matching_nodes) == 1
        assert matching_nodes[0].tags == ["politics"]

    def test_query_by_tags_no_match(self, populated_graph):
        matching_nodes = populated_graph.query_by_tags(["nonexistent"])
        assert matching_nodes == []

    def test_query_by_location(self, empty_graph):
        loc_id = "loc-123"
        n1 = KnowledgeNode(content="Here", location_id=loc_id)
        n2 = KnowledgeNode(content="There", location_id="loc-999")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        matching_nodes = empty_graph.query_by_location(loc_id)
        assert len(matching_nodes) == 1
        assert matching_nodes[0].uuid == n1.uuid

    def test_get_related_bfs(self, empty_graph):
        n1 = KnowledgeNode(content="Root")
        n2 = KnowledgeNode(content="Child")
        n3 = KnowledgeNode(content="Grandchild")
        for node in (n1, n2, n3):
            empty_graph.add_node(node)
        empty_graph.add_edge(n1.uuid, n2.uuid, EdgeType.RELATED_TO)
        empty_graph.add_edge(n2.uuid, n3.uuid, EdgeType.RELATED_TO)
        related = empty_graph.get_related(n1.uuid, depth=2)
        uuids = {rel_node.uuid for rel_node in related}
        assert n2.uuid in uuids
        assert n3.uuid in uuids

    def test_get_related_unknown_node_returns_empty(self, empty_graph):
        assert empty_graph.get_related("ghost") == []

    def test_serialise_round_trip(self, populated_graph):
        graph_dict = populated_graph.to_dict()
        restored = KnowledgeGraph.from_dict(graph_dict)
        assert restored.node_count == populated_graph.node_count


# ---------------------------------------------------------------------------
# KnowledgeQueryEngine
# ---------------------------------------------------------------------------


class TestKnowledgeQueryEngine:
    def test_query_all_world_scope(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        filt = KnowledgeFilter(max_scope=KnowledgeScope.WORLD)
        matching_nodes = engine.query(filt)
        assert len(matching_nodes) == 3  # all three nodes

    def test_query_filters_by_scope(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        filt = KnowledgeFilter(max_scope=KnowledgeScope.LOCAL)
        matching_nodes = engine.query(filt)
        # Only the LOCAL node should pass
        assert all(node.scope == KnowledgeScope.LOCAL for node in matching_nodes)

    def test_query_filters_by_education(self, empty_graph):
        low_node = KnowledgeNode(content="Common knowledge", required_education=0)
        high_node = KnowledgeNode(content="Scholar knowledge", required_education=8)
        empty_graph.add_node(low_node)
        empty_graph.add_node(high_node)
        engine = KnowledgeQueryEngine(empty_graph)
        filt = KnowledgeFilter(max_education_required=3)
        matching_nodes = engine.query(filt)
        uuids = {node.uuid for node in matching_nodes}
        assert low_node.uuid in uuids
        assert high_node.uuid not in uuids

    def test_query_filters_by_source(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        filt = KnowledgeFilter(sources=[KnowledgeSource.FACT])
        matching_nodes = engine.query(filt)
        assert all(node.source == KnowledgeSource.FACT for node in matching_nodes)

    def test_query_filters_by_tag(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        filt = KnowledgeFilter(tags=["trade"])
        matching_nodes = engine.query(filt)
        assert len(matching_nodes) == 1
        assert "trade" in matching_nodes[0].tags

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

    def test_npc_filter_unknown_scope_defaults_local(self):
        npc = Character(name="Mystery", knowledge_scope="galaxy")
        graph = KnowledgeGraph()
        engine = KnowledgeQueryEngine(graph)
        filt = engine.build_npc_filter(npc)
        assert filt.max_scope == KnowledgeScope.LOCAL

    def test_empty_graph_returns_default_message(self, empty_graph):
        engine = KnowledgeQueryEngine(empty_graph)
        npc = Character(name="Joe", knowledge_scope="world")
        ctx = engine.get_context_for_npc(npc)
        assert "don't have any specific knowledge" in ctx

    def test_get_context_prefixes_rumours(self, populated_graph):
        engine = KnowledgeQueryEngine(populated_graph)
        npc = Character(
            name="Gossip",
            knowledge_scope="world",
            attributes={"education": 10, "social_status": 10},
        )
        ctx = engine.get_context_for_npc(npc)
        assert "[Rumour]" in ctx

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
