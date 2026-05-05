"""Tests for MemoryEvent.tags persistence + get_memories_about_concept."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import allure
import pytest

from knowledge import salience as salience_presets
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryEvent, MemoryManager
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from knowledge.query import KnowledgeQueryEngine
from tests._uuid_helpers import make_uuid

pytestmark = [
    allure.epic("Memory & Persistence"),
    allure.feature("Memory event tags"),
]

_HOLDER_A = make_uuid("npc-marcus")
_HOLDER_B = make_uuid("npc-cassia")
_FORUM = make_uuid("forum")
_FLAME_TAG = "light_without_flame"
_FIRE_TAG = "light_without_fire"
_PHOTO_TAG = "image_capture"
_CARRIAGE_TAG = "metal_carriage"


def _attach_tagged_memory(
    graph: KnowledgeGraph,
    holder_id: UUID,
    text: str,
    tags: list[str],
    timestamp: float,
) -> KnowledgeNode:
    """Create a PERSONAL_EXPERIENCE memory node with *tags* and link it to *holder_id*."""
    return _attach_node(
        graph,
        holder_id,
        KnowledgeNode(
            text=text,
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            canon=CanonSource.SESSION,
            timestamp=timestamp,
            salience=salience_presets.DEFAULT,
            tags=tags,
        ),
    )


def _attach_node(graph: KnowledgeGraph, holder_id: UUID, node: KnowledgeNode) -> KnowledgeNode:
    """Persist *node* and witness it from *holder_id*."""
    graph.add_node(node)
    graph.add_edge(holder_id, node.uuid, EdgeType.WITNESSED)
    return node


@allure.story("MemoryEvent.tags")
class TestMemoryEventTagsThreading:
    @allure.title("MemoryEvent.tags defaults to an empty list")
    def test_default_is_empty_list(self):
        event = MemoryEvent(
            event_description="something",
            witness_ids=[_HOLDER_A],
            scope=KnowledgeScope.LOCAL,
        )
        assert event.tags == []

    @allure.title("MemoryEvent default tag list is per-instance, not a shared mutable")
    def test_default_tag_list_is_per_instance(self):
        first = MemoryEvent(
            event_description="a",
            witness_ids=[_HOLDER_A],
            scope=KnowledgeScope.LOCAL,
        )
        first.tags.append("oops")
        second = MemoryEvent(
            event_description="b",
            witness_ids=[_HOLDER_A],
            scope=KnowledgeScope.LOCAL,
        )
        assert second.tags == []

    @allure.title("LOCAL create_memory_from_event threads tags onto the shared personal node")
    @pytest.mark.asyncio
    async def test_local_event_persists_tags(self):
        graph = KnowledgeGraph()
        manager = MemoryManager(graph=graph, llm_client=AsyncMock())

        memory_result = await manager.create_memory_from_event(
            MemoryEvent(
                event_description="player tapped a glowing tablet",
                witness_ids=[_HOLDER_A, _HOLDER_B],
                scope=KnowledgeScope.LOCAL,
                location_id=_FORUM,
                game_time=1.0,
                tags=[_FLAME_TAG, _PHOTO_TAG],
            ),
        )

        canonical = graph.get_node(memory_result.canonical_id)
        assert canonical is not None
        assert canonical.tags == [_FLAME_TAG, _PHOTO_TAG]

    @allure.title("CITY-scope create_memory_from_event threads tags onto broadcast + personal nodes")
    @pytest.mark.asyncio
    async def test_broadcast_event_persists_tags_on_every_node(self):
        graph = KnowledgeGraph()
        manager = MemoryManager(graph=graph, llm_client=AsyncMock())

        memory_result = await manager.create_memory_from_event(
            MemoryEvent(
                event_description="a foreign sorcerer carried a cold-light tablet",
                witness_ids=[_HOLDER_A],
                scope=KnowledgeScope.CITY,
                location_id=_FORUM,
                game_time=2.0,
                tags=[_FLAME_TAG],
            ),
        )

        assert len(memory_result.all_ids) == 2
        for node_id in memory_result.all_ids:
            node = graph.get_node(node_id)
            assert node is not None
            assert node.tags == [_FLAME_TAG]

    @allure.title("Mutating the persisted node's tag list does not mutate the source MemoryEvent")
    @pytest.mark.asyncio
    async def test_persisted_tags_are_decoupled_from_source_list(self):
        graph = KnowledgeGraph()
        manager = MemoryManager(graph=graph, llm_client=AsyncMock())
        source_tags = [_FLAME_TAG]
        memory_result = await manager.create_memory_from_event(
            MemoryEvent(
                event_description="event",
                witness_ids=[_HOLDER_A],
                scope=KnowledgeScope.LOCAL,
                tags=source_tags,
            ),
        )

        canonical = graph.get_node(memory_result.canonical_id)
        canonical.tags.append("downstream-mutation")
        assert source_tags == [_FLAME_TAG]


@allure.story("get_memories_about_concept")
class TestGetMemoriesAboutConcept:
    @allure.title("Exact-match concept tag returns the holder's tagged memory")
    def test_exact_match_returns_tagged_memory(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        flame = _attach_tagged_memory(graph, _HOLDER_A, "tablet glowed", [_FLAME_TAG], timestamp=1.0)
        _attach_tagged_memory(graph, _HOLDER_A, "wagon clattered", [_CARRIAGE_TAG], timestamp=2.0)

        engine = KnowledgeQueryEngine(graph)
        memories = engine.get_memories_about_concept(_HOLDER_A, _FLAME_TAG)

        assert [memory.uuid for memory in memories] == [flame.uuid]

    @allure.title("Fuzzy match above threshold pulls in classifier-drifted concept tags")
    def test_fuzzy_match_above_threshold(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        stored = _attach_tagged_memory(
            graph,
            _HOLDER_A,
            "tablet glowed without flame",
            [_FLAME_TAG],
            timestamp=1.0,
        )

        engine = KnowledgeQueryEngine(graph)
        memories = engine.get_memories_about_concept(_HOLDER_A, _FIRE_TAG)

        assert [memory.uuid for memory in memories] == [stored.uuid]

    @allure.title("Below-threshold concept tags are rejected")
    def test_below_threshold_rejected(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        _attach_tagged_memory(graph, _HOLDER_A, "wagon clattered", [_CARRIAGE_TAG], timestamp=1.0)

        engine = KnowledgeQueryEngine(graph)
        assert engine.get_memories_about_concept(_HOLDER_A, _FLAME_TAG) == []

    @allure.title("Caller may tighten the fuzzy threshold to demand exact matches")
    def test_threshold_is_caller_overridable(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        _attach_tagged_memory(graph, _HOLDER_A, "tablet glowed", [_FLAME_TAG], timestamp=1.0)

        engine = KnowledgeQueryEngine(graph)
        loose = engine.get_memories_about_concept(_HOLDER_A, _FIRE_TAG, fuzzy_threshold=0.85)
        strict = engine.get_memories_about_concept(_HOLDER_A, _FIRE_TAG, fuzzy_threshold=0.99)
        assert len(loose) == 1
        assert strict == []

    @allure.title("Concept query is scoped to the holder, not the whole graph")
    def test_scoped_to_holder(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        graph.register_actor_node(_HOLDER_B, label="Cassia")
        _attach_tagged_memory(graph, _HOLDER_B, "tablet glowed", [_FLAME_TAG], timestamp=1.0)

        engine = KnowledgeQueryEngine(graph)
        assert engine.get_memories_about_concept(_HOLDER_A, _FLAME_TAG) == []

    @allure.title("Concept results are ranked by salience+recency, with limit honouring the cap")
    def test_results_ranked_by_salience_and_recency(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        # High salience + older timestamp should still outrank routine + fresh under
        # the 0.7 salience / 0.3 recency blend.
        pivotal = _attach_node(
            graph,
            _HOLDER_A,
            KnowledgeNode(
                text="the prefect collapsed",
                scope=KnowledgeScope.LOCAL,
                source=KnowledgeSource.PERSONAL_EXPERIENCE,
                canon=CanonSource.SESSION,
                timestamp=1.0,
                salience=salience_presets.COMBAT,
                tags=[_FLAME_TAG],
            ),
        )
        routine = _attach_node(
            graph,
            _HOLDER_A,
            KnowledgeNode(
                text="tablet glowed again",
                scope=KnowledgeScope.LOCAL,
                source=KnowledgeSource.PERSONAL_EXPERIENCE,
                canon=CanonSource.SESSION,
                timestamp=2.0,
                salience=salience_presets.ROUTINE_DIALOGUE,
                tags=[_FLAME_TAG],
            ),
        )

        engine = KnowledgeQueryEngine(graph)
        ranked = engine.get_memories_about_concept(_HOLDER_A, _FLAME_TAG)
        assert [memory.uuid for memory in ranked] == [pivotal.uuid, routine.uuid]

        capped = engine.get_memories_about_concept(_HOLDER_A, _FLAME_TAG, limit=1)
        assert [memory.uuid for memory in capped] == [pivotal.uuid]

    @allure.title("A memory with no tags is invisible to concept queries")
    def test_untagged_memory_does_not_match(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        _attach_tagged_memory(graph, _HOLDER_A, "anonymous moment", [], timestamp=1.0)

        engine = KnowledgeQueryEngine(graph)
        assert engine.get_memories_about_concept(_HOLDER_A, _FLAME_TAG) == []


@allure.story("Salience preset")
class TestAnachronismSaliencePreset:
    @allure.title("ANACHRONISM_ENCOUNTER preset sits between routine chatter and combat")
    def test_preset_falls_between_chatter_and_combat(self):
        assert salience_presets.ROUTINE_DIALOGUE < salience_presets.ANACHRONISM_ENCOUNTER
        assert salience_presets.ANACHRONISM_ENCOUNTER < salience_presets.COMBAT
