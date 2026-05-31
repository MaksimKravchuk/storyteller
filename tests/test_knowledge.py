"""Tests for the knowledge subsystem: node, graph, query engine."""

from __future__ import annotations

from uuid import UUID

import allure
import pytest
from pydantic import ValidationError

from knowledge.graph import KnowledgeGraph
from knowledge import graph_serialization
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from knowledge.query import (
    KnowledgeFilter,
    KnowledgeQueryEngine,
    _RECENCY_TAU_HOURS,
    _memory_score,
)
from models.character import Character
from tests._uuid_helpers import make_uuid

_NPC_1 = make_uuid("npc-1")
_NPC_2 = make_uuid("npc-2")
_NPC_3 = make_uuid("npc-3")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POLITICS = "politics"


def _local_character(name: str, npc_id: UUID, location_id: UUID) -> Character:
    npc = Character(
        name=name,
        knowledge_scope="local",
        attributes={"education": 10},
        location_id=location_id,
    )
    npc.uuid = npc_id
    return npc


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
    @allure.title("A KnowledgeNode gets a UUID assigned on init")
    def test_default_uuid(self):
        node = KnowledgeNode(text="Test fact")
        assert isinstance(node.uuid, UUID)

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

    @allure.story("Salience")
    @allure.title("A KnowledgeNode defaults its salience to the neutral midpoint 0.5")
    def test_default_salience(self):
        node = KnowledgeNode(text="Generic fact")
        assert node.salience == pytest.approx(0.5)

    @allure.story("Salience")
    @allure.title("A KnowledgeNode accepts an explicit salience score in the [0, 1] range")
    def test_custom_salience(self):
        node = KnowledgeNode(text="Witnessed a clash", salience=0.85)
        assert node.salience == pytest.approx(0.85)

    @allure.story("Salience")
    @allure.title("A KnowledgeNode rejects salience outside the [0, 1] range")
    def test_salience_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            KnowledgeNode(text="too hot", salience=1.5)
        with pytest.raises(ValidationError):
            KnowledgeNode(text="too cold", salience=-0.1)

    @allure.story("Salience")
    @allure.title("A KnowledgeNode accepts salience at the inclusive bounds 0.0 and 1.0")
    def test_salience_accepts_inclusive_bounds(self):
        assert KnowledgeNode(text="zero", salience=float(0)).salience == pytest.approx(0)
        assert KnowledgeNode(text="one", salience=float(1)).salience == pytest.approx(1)


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

    @allure.story("Node CRUD")
    @allure.title("register_actor_node stores the passed label as a networkx node attribute")
    def test_register_actor_node_stores_label(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        # The debug label must be persisted verbatim on the node — neither
        # dropped nor coerced to None.
        assert empty_graph.digraph.nodes[_NPC_1]["label"] == "Guard"


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

    @allure.story("Edge CRUD")
    @allure.title("get_edges_from preserves the exact edge_type stored on each outgoing edge")
    def test_get_edges_from_preserves_stored_edge_type(self, empty_graph):
        n1 = KnowledgeNode(text="A")
        n2 = KnowledgeNode(text="B")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        empty_graph.add_edge(n1.uuid, n2.uuid, EdgeType.TOLD_BY)
        edges = empty_graph.get_edges_from(n1.uuid)
        # The stored TOLD_BY must survive the round-trip — a fallback to a
        # different default (e.g. WITNESSED or None) would corrupt it.
        assert edges == [(n2.uuid, EdgeType.TOLD_BY)]

    @allure.story("Edge metadata")
    @allure.title("add_edge treats edge_type as reserved even if metadata contains the same key")
    def test_add_edge_metadata_cannot_override_edge_type(self, empty_graph):
        n1 = KnowledgeNode(text="A")
        n2 = KnowledgeNode(text="B")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        empty_graph.add_edge(
            n1.uuid,
            n2.uuid,
            EdgeType.TOLD_BY,
            metadata={
                "edge_type": EdgeType.WITNESSED,
                "recipient_id": _NPC_1,
            },
        )

        assert empty_graph.get_edges_from(n1.uuid) == [(n2.uuid, EdgeType.TOLD_BY)]
        assert empty_graph.get_edge_metadata(n1.uuid, n2.uuid) == {"recipient_id": _NPC_1}

    @allure.story("Edge CRUD")
    @allure.title("get_edges_from falls back to WITNESSED for an edge stored without an edge_type")
    def test_get_edges_from_defaults_missing_edge_type_to_witnessed(self, empty_graph):
        n1 = KnowledgeNode(text="A")
        n2 = KnowledgeNode(text="B")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        # A raw edge with no ``edge_type`` attribute exercises the ``.get``
        # default branch, which must resolve to WITNESSED (not None).
        empty_graph.digraph.add_edge(n1.uuid, n2.uuid)
        edges = empty_graph.get_edges_from(n1.uuid)
        assert edges == [(n2.uuid, EdgeType.WITNESSED)]

    @allure.story("Edge flags")
    @allure.title("edge_has_flag returns False for a from_id that is not in the graph at all")
    def test_edge_has_flag_missing_from_id_returns_false(self, empty_graph):
        n2 = KnowledgeNode(text="B")
        empty_graph.add_node(n2)
        # `from_id` absent: the short-circuit must return False rather than
        # indexing digraph[from_id] and raising KeyError.
        assert empty_graph.edge_has_flag("ghost-from", n2.uuid, "any_flag") is False

    @allure.story("Edge flags")
    @allure.title("edge_has_flag round-trips a flag set by flag_edge and reads False when unset")
    def test_flag_edge_then_edge_has_flag(self, empty_graph):
        n1 = KnowledgeNode(text="A")
        n2 = KnowledgeNode(text="B")
        empty_graph.add_node(n1)
        empty_graph.add_node(n2)
        empty_graph.add_edge(n1.uuid, n2.uuid, EdgeType.WITNESSED)
        assert empty_graph.edge_has_flag(n1.uuid, n2.uuid, "seen") is False
        empty_graph.flag_edge(n1.uuid, n2.uuid, "seen")
        assert empty_graph.edge_has_flag(n1.uuid, n2.uuid, "seen") is True

    @allure.story("Edge flags")
    @allure.title("flag_edge is a silent no-op when the from_id exists but the to_id edge does not")
    def test_flag_edge_noop_when_edge_absent(self, empty_graph):
        present = KnowledgeNode(text="present")
        empty_graph.add_node(present)
        # `present` is in the graph but has no edge to this target — flag_edge
        # must not raise (a short-circuit using `or` would index the missing
        # edge and raise KeyError).
        empty_graph.flag_edge(present.uuid, "ghost-to", "seen")
        assert empty_graph.edge_has_flag(present.uuid, "ghost-to", "seen") is False


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

    @allure.story("Query engine filters")
    @allure.title("A node whose required_education equals the filter limit is visible (inclusive bound)")
    def test_query_education_at_boundary_is_visible(self, empty_graph):
        at_bound = KnowledgeNode(text="Exactly at the limit", required_education=3)
        empty_graph.add_node(at_bound)
        engine = KnowledgeQueryEngine(empty_graph)
        matched_uuids = {node.uuid for node in engine.query(KnowledgeFilter(max_education_required=3))}
        # required_education == max must pass: the comparison is <=, not <.
        assert at_bound.uuid in matched_uuids

    @allure.story("Query engine filters")
    @allure.title("A LOCAL node at a different location is excluded when the filter pins a location_id")
    def test_query_local_node_excluded_by_location(self, empty_graph):
        here = make_uuid("loc-here")
        elsewhere = make_uuid("loc-elsewhere")
        local_here = KnowledgeNode(text="here", scope=KnowledgeScope.LOCAL, location_id=here)
        local_elsewhere = KnowledgeNode(text="elsewhere", scope=KnowledgeScope.LOCAL, location_id=elsewhere)
        empty_graph.add_node(local_here)
        empty_graph.add_node(local_elsewhere)
        engine = KnowledgeQueryEngine(empty_graph)
        matched_uuids = {node.uuid for node in engine.query(KnowledgeFilter(location_id=here))}
        # The filter's location_id must reach passes_location: the LOCAL node
        # anchored elsewhere is gated out, the matching one stays.
        assert local_here.uuid in matched_uuids
        assert local_elsewhere.uuid not in matched_uuids

    @allure.story("Query engine filters")
    @allure.title("A located LOCAL node stays visible when the filter carries no location_id")
    def test_query_local_node_visible_without_filter_location(self, empty_graph):
        somewhere = make_uuid("loc-somewhere")
        local_node = KnowledgeNode(text="anchored", scope=KnowledgeScope.LOCAL, location_id=somewhere)
        empty_graph.add_node(local_node)
        engine = KnowledgeQueryEngine(empty_graph)
        # filt.location_id is None while the node has a location: the "either
        # side falsy" guard must short-circuit to visible.
        matched_uuids = {node.uuid for node in engine.query(KnowledgeFilter())}
        assert local_node.uuid in matched_uuids


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
    @allure.title("build_npc_filter maps the 'city' and 'country' scope strings to their KnowledgeScope")
    def test_build_npc_filter_maps_city_and_country(self):
        graph = KnowledgeGraph()
        engine = KnowledgeQueryEngine(graph)
        city_npc = Character(name="Citizen", knowledge_scope="city")
        country_npc = Character(name="Noble", knowledge_scope="country")
        # The scope_map keys must be the exact lowercase strings — a mangled
        # key would silently fall through to the LOCAL default.
        assert engine.build_npc_filter(city_npc).max_scope == KnowledgeScope.CITY
        assert engine.build_npc_filter(country_npc).max_scope == KnowledgeScope.COUNTRY

    @allure.story("NPC context building")
    @allure.title("build_npc_filter defaults missing education to 3 and copies location_id and npc_id verbatim")
    def test_build_npc_filter_copies_identity_fields(self):
        npc_location = make_uuid("npc-loc")
        npc = Character(name="Local", knowledge_scope="local", location_id=npc_location)
        graph = KnowledgeGraph()
        engine = KnowledgeQueryEngine(graph)
        filt = engine.build_npc_filter(npc)
        # No education attribute set → the literal default 3 must apply.
        assert filt.max_education_required == 3
        # location_id and npc_id are threaded through, not dropped/nulled.
        assert filt.location_id == npc_location
        assert filt.npc_id == npc.uuid

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
        # Exact text and casing matter: this is the literal fallback line.
        assert ctx == "You don't have any specific knowledge about this topic."

    @allure.story("NPC context building")
    @allure.title("get_context_for_npc renders a FACT node with no source prefix and an empty-string default")
    def test_get_context_fact_node_has_no_prefix(self, empty_graph):
        empty_graph.add_node(KnowledgeNode(text="Rome is ancient", scope=KnowledgeScope.WORLD))
        engine = KnowledgeQueryEngine(empty_graph)
        npc = Character(name="Scholar", knowledge_scope="world", attributes={"education": 10})
        ctx = engine.get_context_for_npc(npc)
        # FACT is absent from the prefix map, so it falls back to "" — the
        # line is exactly "- <text>" with no "None"/placeholder prefix.
        assert ctx == "- Rome is ancient"

    @allure.story("NPC context building")
    @allure.title("get_context_for_npc orders PERSONAL_EXPERIENCE ahead of RUMOR and joins lines with a newline")
    def test_get_context_orders_by_source_priority(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        # Add a RUMOR first, then the personal memory, so insertion order is
        # the reverse of the desired priority order — only a correct
        # priority-keyed sort produces personal-before-rumor.
        empty_graph.add_node(
            KnowledgeNode(text="conspiracy afoot", scope=KnowledgeScope.WORLD, source=KnowledgeSource.RUMOR),
        )
        memory = KnowledgeNode(
            text="I saw it myself",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            timestamp=1.0,
        )
        empty_graph.add_node(memory)
        empty_graph.add_edge(_NPC_1, memory.uuid, EdgeType.WITNESSED)
        npc = Character(name="Watcher", knowledge_scope="world", attributes={"education": 10})
        npc.uuid = _NPC_1
        ctx = KnowledgeQueryEngine(empty_graph).get_context_for_npc(npc)
        expected = "\n".join(["- [Personal experience] I saw it myself", "- [Rumour] conspiracy afoot"])
        assert ctx == expected

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
    npc_id: UUID,
    text: str,
    timestamp: float,
    salience: float = 0.5,
) -> KnowledgeNode:
    """Helper: add a PERSONAL_EXPERIENCE node and link it to an NPC via WITNESSED."""
    memory = KnowledgeNode(
        text=text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        timestamp=timestamp,
        salience=salience,
    )
    memory_id = graph.add_node(memory)
    graph.add_edge(npc_id, memory_id, EdgeType.WITNESSED)
    return memory


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestQueryEnginePersonalMemoryInclusion:
    @allure.story("Query engine filters")
    @allure.title("A query with npc_id appends a personal memory that the scope/education filters would exclude")
    def test_query_includes_npc_personal_memory(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        # required_education far above the filter limit means _node_matches
        # rejects it, so its presence is solely due to append_personal_memories
        # running for the npc_id.
        memory = KnowledgeNode(
            text="I watched the secret duel",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            required_education=9,
            timestamp=1.0,
        )
        empty_graph.add_node(memory)
        empty_graph.add_edge(_NPC_1, memory.uuid, EdgeType.WITNESSED)
        engine = KnowledgeQueryEngine(empty_graph)
        filt = KnowledgeFilter(max_education_required=2, npc_id=_NPC_1)
        matched_uuids = {node.uuid for node in engine.query(filt)}
        assert memory.uuid in matched_uuids

    @allure.story("Query engine filters")
    @allure.title("A scope-matched world fact plus an NPC's personal memory both appear without duplication")
    def test_query_personal_memory_not_duplicated(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        world_fact = KnowledgeNode(text="The empire is vast", scope=KnowledgeScope.WORLD)
        empty_graph.add_node(world_fact)
        memory = _attach_memory(empty_graph, _NPC_1, "I watched the duel", timestamp=1.0)
        engine = KnowledgeQueryEngine(empty_graph)
        matched = engine.query(KnowledgeFilter(npc_id=_NPC_1))
        matched_uuids = [node.uuid for node in matched]
        assert world_fact.uuid in matched_uuids
        # The personal memory is appended exactly once (the "not already in
        # the result" guard must keep it, and not re-add scope-matched nodes).
        assert matched_uuids.count(memory.uuid) == 1


@allure.epic("Knowledge Graph")
@allure.feature("Knowledge query")
class TestRecipientOwnedHearsayVisibility:
    @allure.story("HEARSAY ownership")
    @allure.title("Recipient-owned HEARSAY is visible only to the recipient NPC")
    def test_recipient_owned_hearsay_visible_only_to_recipient_context(self, empty_graph):
        location_id = make_uuid("shared-location")
        hearsay = KnowledgeNode(
            text="Only Livia heard the guard's warning.",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.HEARSAY,
            location_id=location_id,
        )
        empty_graph.add_node(hearsay)
        empty_graph.add_edge(
            hearsay.uuid,
            make_uuid("rumor-source"),
            EdgeType.TOLD_BY,
            metadata={"recipient_id": _NPC_1},
        )
        engine = KnowledgeQueryEngine(empty_graph)

        recipient_context = engine.get_context_for_npc(_local_character("Livia", _NPC_1, location_id))
        nonrecipient_context = engine.get_context_for_npc(_local_character("Claudia", _NPC_2, location_id))

        assert hearsay.text in recipient_context
        assert hearsay.text not in nonrecipient_context

    @allure.story("HEARSAY ownership")
    @allure.title("A HEARSAY node with several recipient edges is visible to every matching recipient")
    def test_hearsay_with_multiple_recipient_edges_is_visible_to_any_matching_recipient(self, empty_graph):
        location_id = make_uuid("shared-location")
        hearsay = KnowledgeNode(
            text="Livia and Claudia both heard the guard's warning.",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.HEARSAY,
            location_id=location_id,
        )
        empty_graph.add_node(hearsay)
        empty_graph.add_edge(
            hearsay.uuid,
            make_uuid("rumor-source-livia"),
            EdgeType.TOLD_BY,
            metadata={"recipient_id": _NPC_1},
        )
        empty_graph.add_edge(
            hearsay.uuid,
            make_uuid("rumor-source-claudia"),
            EdgeType.TOLD_BY,
            metadata={"recipient_id": _NPC_2},
        )
        engine = KnowledgeQueryEngine(empty_graph)

        first_context = engine.get_context_for_npc(_local_character("Livia", _NPC_1, location_id))
        second_context = engine.get_context_for_npc(_local_character("Claudia", _NPC_2, location_id))
        third_context = engine.get_context_for_npc(_local_character("Julia", _NPC_3, location_id))

        assert hearsay.text in first_context
        assert hearsay.text in second_context
        assert hearsay.text not in third_context

    @allure.story("HEARSAY ownership")
    @allure.title("Legacy HEARSAY without recipient_id remains location-visible")
    def test_legacy_hearsay_without_recipient_id_remains_location_visible(self, empty_graph):
        location_id = make_uuid("shared-location")
        hearsay = KnowledgeNode(
            text="Everyone at the tavern heard the old rumor.",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.HEARSAY,
            location_id=location_id,
        )
        empty_graph.add_node(hearsay)
        empty_graph.add_edge(hearsay.uuid, make_uuid("rumor-source"), EdgeType.TOLD_BY)
        engine = KnowledgeQueryEngine(empty_graph)

        first_context = engine.get_context_for_npc(_local_character("Livia", _NPC_1, location_id))
        second_context = engine.get_context_for_npc(_local_character("Claudia", _NPC_2, location_id))

        assert hearsay.text in first_context
        assert hearsay.text in second_context

    @allure.story("HEARSAY ownership")
    @allure.title("Generic location queries keep recipient-owned HEARSAY visible")
    def test_generic_location_query_keeps_recipient_owned_hearsay_visible(self, empty_graph):
        location_id = make_uuid("shared-location")
        hearsay = KnowledgeNode(
            text="Livia heard the guard's warning.",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.HEARSAY,
            location_id=location_id,
        )
        empty_graph.add_node(hearsay)
        empty_graph.add_edge(
            hearsay.uuid,
            make_uuid("rumor-source"),
            EdgeType.TOLD_BY,
            metadata={"recipient_id": _NPC_1},
        )

        matched = KnowledgeQueryEngine(empty_graph).query(
            KnowledgeFilter(max_scope=KnowledgeScope.LOCAL, location_id=location_id),
        )

        assert [node.uuid for node in matched] == [hearsay.uuid]

    @allure.story("HEARSAY ownership")
    @allure.title("Malformed recipient metadata does not match an NPC-scoped query")
    def test_malformed_recipient_metadata_does_not_match_npc_query(self, empty_graph):
        location_id = make_uuid("shared-location")
        hearsay = KnowledgeNode(
            text="A malformed recipient id should not leak this rumor.",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.HEARSAY,
            location_id=location_id,
        )
        empty_graph.add_node(hearsay)
        empty_graph.add_edge(
            hearsay.uuid,
            make_uuid("rumor-source"),
            EdgeType.TOLD_BY,
            metadata={"recipient_id": "not-a-uuid"},
        )

        context = KnowledgeQueryEngine(empty_graph).get_context_for_npc(
            _local_character("Livia", _NPC_1, location_id),
        )

        assert hearsay.text not in context


@allure.epic("Memory & Persistence")
@allure.feature("Memory query")
class TestQueryEngineGetMemoriesHeldBy:
    @allure.story("get_memories_held_by")
    @allure.title("get_memories_held_by returns an empty list for a graph with no memory edges")
    def test_empty_graph_returns_empty(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        engine = KnowledgeQueryEngine(empty_graph)
        assert engine.get_memories_held_by(_NPC_1) == []

    @allure.story("get_memories_held_by")
    @allure.title("get_memories_held_by returns a single PERSONAL_EXPERIENCE node linked to the NPC via WITNESSED")
    def test_single_memory_returned(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        memory = _attach_memory(empty_graph, _NPC_1, "Met a kind traveller", timestamp=1.0)

        engine = KnowledgeQueryEngine(empty_graph)
        memories = engine.get_memories_held_by(_NPC_1)

        assert len(memories) == 1
        assert memories[0].uuid == memory.uuid

    @allure.story("get_memories_held_by")
    @allure.title("get_memories_held_by caps the result at the requested limit")
    def test_limit_respected(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        for idx in range(5):
            _attach_memory(empty_graph, _NPC_1, f"memory-{idx}", timestamp=float(idx))

        engine = KnowledgeQueryEngine(empty_graph)
        assert len(engine.get_memories_held_by(_NPC_1, limit=2)) == 2

    @allure.story("get_memories_held_by")
    @allure.title("get_memories_held_by orders equal-salience memories by timestamp descending (newest first)")
    def test_orders_by_timestamp_descending(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        _attach_memory(empty_graph, _NPC_1, "oldest", timestamp=1.0)
        _attach_memory(empty_graph, _NPC_1, "newest", timestamp=3.0)
        _attach_memory(empty_graph, _NPC_1, "middle", timestamp=2.0)

        engine = KnowledgeQueryEngine(empty_graph)
        ordered_texts = [mem.text for mem in engine.get_memories_held_by(_NPC_1)]
        assert ordered_texts == ["newest", "middle", "oldest"]

    @allure.story("get_memories_held_by")
    @allure.title("A high-salience pivotal memory survives the top-K cut despite being older than routine chatter")
    def test_high_salience_outranks_recent_routine(self, empty_graph):
        """Regression: pure-recency ordering crowded out pivotal events.

        With limit=5 and 5 newer routine memories plus 1 older
        pivotal memory, pure-recency ranking returns only the 5
        routine memories. Salience-aware ranking must keep the
        pivotal memory in the result set.
        """
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        _attach_memory(empty_graph, _NPC_1, "witnessed-murder", timestamp=10.0, salience=0.95)
        for idx in range(5):
            _attach_memory(
                empty_graph,
                _NPC_1,
                "small-talk-{0}".format(idx),
                timestamp=11.0 + idx,
                salience=0.3,
            )

        engine = KnowledgeQueryEngine(empty_graph)
        ordered_texts = [mem.text for mem in engine.get_memories_held_by(_NPC_1, limit=5)]
        assert "witnessed-murder" in ordered_texts
        assert ordered_texts[0] == "witnessed-murder"


@allure.epic("Memory & Persistence")
@allure.feature("Memory query")
class TestResolveSubjectIdentityCount:
    @allure.story("resolve_subject_identity")
    @allure.title("resolve_subject_identity returns the total count of memories it backfilled")
    def test_returns_count_of_all_updated(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        first = _attach_memory(empty_graph, _NPC_1, "the stranger paid me", timestamp=1.0)
        second = _attach_memory(empty_graph, _NPC_1, "the stranger left town", timestamp=2.0)
        subject = make_uuid("subject-x")

        updated = empty_graph.resolve_subject_identity(
            holder_id=_NPC_1,
            subject_id=subject,
            predicate=lambda node: "stranger" in node.text,
        )

        # Two anonymous matches resolved → the counter must accumulate to 2,
        # not be reset to a constant 1.
        assert updated == 2
        assert empty_graph.get_node(first.uuid).subject_id == subject
        assert empty_graph.get_node(second.uuid).subject_id == subject


@allure.epic("Memory & Persistence")
@allure.feature("Memory query")
class TestGetMemoriesAboutConceptBoundary:
    @allure.story("get_memories_about_concept")
    @allure.title("A tag whose similarity exactly equals the threshold still matches (inclusive bound)")
    def test_exact_threshold_match_is_inclusive(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        memory = KnowledgeNode(
            text="I learned to spark light without flame",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            timestamp=1.0,
            tags=["light_without_flame"],
        )
        empty_graph.add_node(memory)
        empty_graph.add_edge(_NPC_1, memory.uuid, EdgeType.WITNESSED)
        engine = KnowledgeQueryEngine(empty_graph)
        # An identical tag scores ratio 1.0; at threshold 1.0 the comparison
        # must be >= (inclusive), so the memory is still returned.
        matched = engine.get_memories_about_concept(_NPC_1, "light_without_flame", fuzzy_threshold=1.0)
        assert [mem.uuid for mem in matched] == [memory.uuid]


@allure.epic("Memory & Persistence")
@allure.feature("Memory query")
class TestGetMemoriesAboutSubjectLimit:
    @allure.story("get_memories_about_subject")
    @allure.title("get_memories_about_subject caps the result at an explicit limit")
    def test_explicit_limit_caps_results(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        subject = make_uuid("subject-y")
        for idx in range(3):
            memory = KnowledgeNode(
                text="encounter-{0}".format(idx),
                scope=KnowledgeScope.LOCAL,
                source=KnowledgeSource.PERSONAL_EXPERIENCE,
                timestamp=float(idx),
                subject_id=subject,
            )
            empty_graph.add_node(memory)
            empty_graph.add_edge(_NPC_1, memory.uuid, EdgeType.WITNESSED)

        engine = KnowledgeQueryEngine(empty_graph)
        # limit is not None, so the result must be sliced down to 2.
        assert len(engine.get_memories_about_subject(_NPC_1, subject, limit=2)) == 2
        # limit None returns every match.
        assert len(engine.get_memories_about_subject(_NPC_1, subject)) == 3


@allure.epic("Memory & Persistence")
@allure.feature("Memory query")
class TestMemoryScoreBlend:
    @allure.story("Salience+recency blend")
    @allure.title("A memory at age zero scores salience*0.7 + 1.0*0.3 with the exact recency coefficient")
    def test_score_at_zero_age(self):
        now = 100.0
        memory = KnowledgeNode(
            text="fresh",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            timestamp=now,
            salience=0.5,
        )
        # age = 0 → recency_factor = 1 - 0/72 = 1.0, so the recency term is the
        # full 0.3 weight (the `2 - age/tau` mutant would push it to 0.6). A
        # half-window check below pins the division form.
        expected = 0.7 * 0.5 + 0.3
        assert _memory_score(memory, now) == pytest.approx(expected)

    @allure.story("Salience+recency blend")
    @allure.title("A memory aged half the recency window decays its recency factor to 0.5")
    def test_score_at_half_window_age(self):
        now = 100.0
        half_window = now - (_RECENCY_TAU_HOURS / 2)
        memory = KnowledgeNode(
            text="half-old",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            timestamp=half_window,
            salience=0.5,
        )
        # age = 36h, tau = 72h → recency_factor = 1 - 36/72 = 0.5. The
        # `age * tau` mutant would give 1 - 36*72 (huge negative → floored to
        # 0), and the `2 - age/tau` mutant would give 1.5 — both differ.
        assert _memory_score(memory, now) == pytest.approx(0.7 * 0.5 + 0.3 * 0.5)

    @allure.story("Salience+recency blend")
    @allure.title("A memory with no timestamp contributes zero recency and is held up by salience alone")
    def test_score_without_timestamp(self):
        no_ts = KnowledgeNode(
            text="undated",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            timestamp=None,
            salience=0.4,
        )
        # With no timestamp the recency factor stays at its zero starting value
        # (a None start would raise inside the 0.3 * recency blend), so the
        # score is salience-weighted only.
        assert _memory_score(no_ts, float(0)) == pytest.approx(0.7 * 0.4)


@allure.epic("Memory & Persistence")
@allure.feature("Memory query")
class TestWitnessMemoryIndex:
    @allure.story("Witness-memory index")
    @allure.title("personal_memories_for returns indexed PERSONAL_EXPERIENCE nodes for the witness")
    def test_index_populated_on_witnessed_edge(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        memory = _attach_memory(empty_graph, _NPC_1, "Met a stranger", timestamp=1.0)

        memories = empty_graph.personal_memories_for(_NPC_1)

        assert [mem.uuid for mem in memories] == [memory.uuid]

    @allure.story("Witness-memory index")
    @allure.title("personal_memories_for keeps witnesses isolated — one NPC's memories don't leak to another")
    def test_index_isolates_witnesses(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        empty_graph.register_actor_node(_NPC_2, label="Innkeeper")
        _attach_memory(empty_graph, _NPC_1, "Saw a fight", timestamp=1.0)
        innkeeper_memory = _attach_memory(empty_graph, _NPC_2, "Heard a song", timestamp=2.0)

        innkeeper_memories = empty_graph.personal_memories_for(_NPC_2)

        assert [mem.uuid for mem in innkeeper_memories] == [innkeeper_memory.uuid]

    @allure.story("Witness-memory index")
    @allure.title("Removing a memory node evicts it from every witness's index entry")
    def test_remove_memory_node_evicts_from_index(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        survivor = _attach_memory(empty_graph, _NPC_1, "lasting", timestamp=1.0)
        ephemeral = _attach_memory(empty_graph, _NPC_1, "removed", timestamp=2.0)

        empty_graph.remove_node(ephemeral.uuid)

        remaining = empty_graph.personal_memories_for(_NPC_1)
        assert [mem.uuid for mem in remaining] == [survivor.uuid]

    @allure.story("Witness-memory index")
    @allure.title("Removing a witness NPC node clears that NPC's index entry but leaves the memory node intact")
    def test_remove_witness_clears_index_entry(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        memory = _attach_memory(empty_graph, _NPC_1, "memory", timestamp=1.0)

        empty_graph.remove_node(_NPC_1)

        assert empty_graph.personal_memories_for(_NPC_1) == []
        assert empty_graph.get_node(memory.uuid) is not None

    @allure.story("Witness-memory index")
    @allure.title("Removing a witness's only memory drops the now-empty witness key from the index")
    def test_remove_only_memory_evicts_empty_witness_key(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        memory = _attach_memory(empty_graph, _NPC_1, "the only thing I saw", timestamp=1.0)
        assert _NPC_1 in empty_graph._witness_memory_index

        empty_graph.remove_node(memory.uuid)

        # The witness's set is now empty, so the witness key itself must be
        # discarded from the index — not left dangling with a stale id.
        assert _NPC_1 not in empty_graph._witness_memory_index

    @allure.story("Witness-memory index")
    @allure.title("Removing one of a witness's two memories keeps the witness key and the surviving memory")
    def test_remove_one_of_two_memories_keeps_witness(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        keep = _attach_memory(empty_graph, _NPC_1, "kept", timestamp=1.0)
        drop = _attach_memory(empty_graph, _NPC_1, "dropped", timestamp=2.0)

        empty_graph.remove_node(drop.uuid)

        # Only the dropped id is discarded; the witness key and the surviving
        # memory id must remain (a discard(None) would leave the dropped id in
        # place instead).
        assert empty_graph._witness_memory_index[_NPC_1] == {keep.uuid}

    @allure.story("Witness-memory index")
    @allure.title("Removing a memory shared by two witnesses evicts it from both index entries")
    def test_remove_shared_memory_evicts_from_all_witnesses(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        empty_graph.register_actor_node(_NPC_2, label="Innkeeper")
        shared = KnowledgeNode(
            text="shared",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            timestamp=1.0,
        )
        shared_id = empty_graph.add_node(shared)
        empty_graph.add_edge(_NPC_1, shared_id, EdgeType.WITNESSED)
        empty_graph.add_edge(_NPC_2, shared_id, EdgeType.WITNESSED)

        empty_graph.remove_node(shared_id)

        assert empty_graph.personal_memories_for(_NPC_1) == []
        assert empty_graph.personal_memories_for(_NPC_2) == []

    @allure.story("Witness-memory index")
    @allure.title("Non-WITNESSED outgoing edges from an NPC to a PERSONAL_EXPERIENCE node are not indexed")
    def test_non_witnessed_outgoing_edge_not_indexed(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Source")
        memory = KnowledgeNode(
            text="dream",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            timestamp=1.0,
        )
        memory_id = empty_graph.add_node(memory)
        empty_graph.add_edge(_NPC_1, memory_id, EdgeType.TOLD_BY)

        assert empty_graph.personal_memories_for(_NPC_1) == []

    @allure.story("Witness-memory index")
    @allure.title("WITNESSED edges to non-PERSONAL_EXPERIENCE nodes are not indexed")
    def test_non_personal_experience_target_is_not_indexed(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        fact = KnowledgeNode(
            text="fact",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.FACT,
            timestamp=1.0,
        )
        fact_id = empty_graph.add_node(fact)
        empty_graph.add_edge(_NPC_1, fact_id, EdgeType.WITNESSED)

        assert empty_graph.personal_memories_for(_NPC_1) == []

    @allure.story("Witness-memory index")
    @allure.title("Round-tripping the graph through to_dict/from_dict rebuilds the witness-memory index")
    def test_index_rebuilt_after_serialisation(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        memory = _attach_memory(empty_graph, _NPC_1, "Met a stranger", timestamp=1.0)

        restored = graph_serialization.from_dict(graph_serialization.to_dict(empty_graph))

        restored_memories = restored.personal_memories_for(_NPC_1)
        assert [mem.uuid for mem in restored_memories] == [memory.uuid]

    @allure.story("Witness-memory index")
    @allure.title("rebuild_witness_memory_index skips a non-PERSONAL target but still indexes a later valid memory")
    def test_rebuild_skips_witnessed_fact_target(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        fact = KnowledgeNode(text="fact", scope=KnowledgeScope.LOCAL, source=KnowledgeSource.FACT)
        memory = KnowledgeNode(
            text="real memory",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            timestamp=1.0,
        )
        empty_graph.add_node(fact)
        empty_graph.add_node(memory)
        # Bypass add_edge's indexing by writing edges directly. The FACT edge
        # is inserted BEFORE the valid memory edge so the rebuild's reject
        # branch must `continue` (skip just the FACT) rather than `break`
        # (which would also drop the valid memory that follows).
        empty_graph.digraph.add_edge(_NPC_1, fact.uuid, edge_type=EdgeType.WITNESSED)
        empty_graph.digraph.add_edge(_NPC_1, memory.uuid, edge_type=EdgeType.WITNESSED)
        empty_graph.rebuild_witness_memory_index()

        # The FACT target requires BOTH "target present" AND "source personal",
        # so it stays out; the valid PERSONAL memory after it is still indexed.
        assert [mem.uuid for mem in empty_graph.personal_memories_for(_NPC_1)] == [memory.uuid]

    @allure.story("Witness-memory index")
    @allure.title("KnowledgeQueryEngine._personal_memories_for delegates to the graph index")
    def test_query_engine_uses_graph_index(self, empty_graph):
        empty_graph.register_actor_node(_NPC_1, label="Guard")
        memory = _attach_memory(empty_graph, _NPC_1, "Met a stranger", timestamp=1.0)

        engine = KnowledgeQueryEngine(empty_graph)
        retrieved = engine.get_memories_held_by(_NPC_1)

        assert [mem.uuid for mem in retrieved] == [memory.uuid]
