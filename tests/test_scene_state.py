"""Tests for knowledge.scene_state — scene-delta read/write helpers (KER-13).

These exercise the graph-side persistence layer used by the INTERACT-
with-object path. ``record_scene_delta`` writes LOCAL/FACT/SESSION
nodes tagged ``scene_state`` + ``location_id``; the query helpers
read them back filtered by location or grouped by location.
"""

from __future__ import annotations

import allure
import pytest

from knowledge.graph import KnowledgeGraph
from knowledge.node import (
    CanonSource,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from knowledge.scene_state import (
    SCENE_STATE_TAG,
    all_scene_deltas,
    query_scene_deltas,
    record_scene_delta,
)
from models.game_state import INITIAL_GAME_CLOCK
from tests._uuid_helpers import make_uuid

_TAVERN = make_uuid("tavern")
_FORUM = make_uuid("forum")


@allure.epic("Scene & Exploration")
@allure.feature("Scene state persistence")
class TestRecordSceneDelta:
    @allure.story("Node attributes")
    @allure.title("record_scene_delta writes a LOCAL/FACT/SESSION node carrying the location_id and scene_state tag")
    def test_record_delta_node_attributes(self):
        graph = KnowledgeGraph()
        node_id = record_scene_delta(
            graph,
            location_id=_TAVERN,
            delta_text="The front window is broken.",
            game_time=12.5,
        )
        node = graph.get_node(node_id)
        assert isinstance(node, KnowledgeNode)
        assert node.text == "The front window is broken."
        assert node.scope == KnowledgeScope.LOCAL
        assert node.source == KnowledgeSource.FACT
        assert node.canon == CanonSource.SESSION
        assert node.location_id == _TAVERN
        assert node.timestamp == pytest.approx(12.5)
        assert SCENE_STATE_TAG in node.tags
        assert str(_TAVERN) in node.tags

    @allure.story("Node attributes")
    @allure.title("record_scene_delta accepts the default game_time when no timestamp is provided")
    def test_record_delta_default_timestamp(self):
        graph = KnowledgeGraph()
        node_id = record_scene_delta(
            graph,
            location_id=_FORUM,
            delta_text="The statue of Jupiter is toppled.",
        )
        node = graph.get_node(node_id)
        assert node is not None
        assert node.timestamp == pytest.approx(INITIAL_GAME_CLOCK)


@allure.epic("Scene & Exploration")
@allure.feature("Scene state persistence")
class TestQuerySceneDeltas:
    @allure.story("Location filtering")
    @allure.title("query_scene_deltas returns only nodes whose location_id matches the query")
    def test_filters_by_location(self):
        graph = KnowledgeGraph()
        record_scene_delta(graph, location_id=_TAVERN, delta_text="Window broken.")
        record_scene_delta(graph, location_id=_FORUM, delta_text="Statue toppled.")
        results = query_scene_deltas(graph, _TAVERN)
        assert len(results) == 1
        assert results[0].text == "Window broken."

    @allure.story("Tag filtering")
    @allure.title("query_scene_deltas ignores nodes that match the location but lack the scene_state tag")
    def test_ignores_non_scene_state_nodes(self):
        graph = KnowledgeGraph()
        # An ambient memory that happens to carry a location id but no scene_state tag.
        graph.add_node(
            KnowledgeNode(
                text="Someone muttered a rumour here.",
                scope=KnowledgeScope.LOCAL,
                source=KnowledgeSource.RUMOR,
                location_id=_TAVERN,
                tags=["rumour"],
            ),
        )
        record_scene_delta(graph, location_id=_TAVERN, delta_text="Window broken.")
        results = query_scene_deltas(graph, _TAVERN)
        assert len(results) == 1
        assert results[0].text == "Window broken."

    @allure.story("Empty graph")
    @allure.title("query_scene_deltas returns an empty list when no deltas have been recorded")
    def test_empty_graph(self):
        graph = KnowledgeGraph()
        assert query_scene_deltas(graph, _TAVERN) == []


@allure.epic("Scene & Exploration")
@allure.feature("Scene state persistence")
class TestAllSceneDeltas:
    @allure.story("Grouping")
    @allure.title("all_scene_deltas groups every scene_state delta by its location_id")
    def test_groups_by_location(self):
        graph = KnowledgeGraph()
        record_scene_delta(graph, location_id=_TAVERN, delta_text="Window broken.")
        record_scene_delta(graph, location_id=_TAVERN, delta_text="Door splintered.")
        record_scene_delta(graph, location_id=_FORUM, delta_text="Statue toppled.")
        grouped = all_scene_deltas(graph)
        assert set(grouped.keys()) == {_TAVERN, _FORUM}
        assert sorted(grouped[_TAVERN]) == ["Door splintered.", "Window broken."]
        assert grouped[_FORUM] == ["Statue toppled."]

    @allure.story("Grouping")
    @allure.title("all_scene_deltas skips scene_state nodes that are missing a location_id")
    def test_skips_unlocated_nodes(self):
        graph = KnowledgeGraph()
        graph.add_node(
            KnowledgeNode(
                text="Dangling delta with no location.",
                scope=KnowledgeScope.LOCAL,
                source=KnowledgeSource.FACT,
                tags=[SCENE_STATE_TAG],
            ),
        )
        record_scene_delta(graph, location_id=_TAVERN, delta_text="Window broken.")
        grouped = all_scene_deltas(graph)
        assert grouped == {_TAVERN: ["Window broken."]}
