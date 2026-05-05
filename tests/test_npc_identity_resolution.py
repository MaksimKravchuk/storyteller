"""Tests for NPC identity resolution across encounters."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import allure
import pytest

from cast import director_dialogue as _dlg_mod, director_object_interaction as _doi_mod, item_generator as _ig_mod
from cast.schemas import item_response as _item_resp
from db.converters.knowledge import knowledge_node_to_row, row_to_knowledge_node
from knowledge import (
    graph as _graph_mod,
    graph_serialization,
    memory as _memory_mod,
    node as _node_mod,
    query as _query_mod,
)
from llm.message import LLMResponse
from models.scene import Scene, SceneNPC
from tests.director_helpers import make_game_state, make_mock_actor, make_uuid, setup_npc

DialogueHandler = _dlg_mod.DialogueHandler
KnowledgeGraph = _graph_mod.KnowledgeGraph
MemoryEvent = _memory_mod.MemoryEvent
MemoryManager = _memory_mod.MemoryManager
CanonSource = _node_mod.CanonSource
EdgeType = _node_mod.EdgeType
KnowledgeNode = _node_mod.KnowledgeNode
KnowledgeScope = _node_mod.KnowledgeScope
KnowledgeSource = _node_mod.KnowledgeSource
KnowledgeQueryEngine = _query_mod.KnowledgeQueryEngine

_HOLDER_A = make_uuid("npc-marcus")
_HOLDER_B = make_uuid("npc-cassia")
_BOB = make_uuid("npc-bob")
_OTHER = make_uuid("npc-other")
_FORUM = make_uuid("forum")
_GAME_STATE_ID = "game-state-1"
_MEMORY_SUMMARY = "Marcus finds the player curious and welcoming."
_STRANGER_MEMORY = "the stranger asked me about the forum"
_OTHER_MEMORY = "the priest blessed the merchants today"


def _attach_memory(
    graph: KnowledgeGraph,
    holder_id: UUID,
    text: str,
    timestamp: float,
    subject_id: UUID | None = None,
) -> KnowledgeNode:
    """Create a PERSONAL_EXPERIENCE memory node and link it to *holder_id*."""
    memory = KnowledgeNode(
        text=text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
        timestamp=timestamp,
        subject_id=subject_id,
    )
    graph.add_node(memory)
    graph.add_edge(holder_id, memory.uuid, EdgeType.WITNESSED)
    return memory


@allure.epic("Memory & Persistence")
@allure.feature("Identity resolution")
class TestKnowledgeNodeSubjectIdField:
    @allure.story("Field default")
    @allure.title("KnowledgeNode.subject_id defaults to None when not supplied")
    def test_subject_id_defaults_to_none(self):
        node = KnowledgeNode(text="anonymous memory")
        assert node.subject_id is None

    @allure.story("Field round-trip")
    @allure.title("KnowledgeNode.subject_id round-trips through graph_serialization to_dict/from_dict")
    def test_subject_id_round_trips_through_graph_serialisation(self):
        graph = KnowledgeGraph()
        identified = KnowledgeNode(
            text="seen with Bob",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            subject_id=_BOB,
        )
        graph.add_node(identified)

        restored = graph_serialization.from_dict(graph_serialization.to_dict(graph))
        recovered = restored.get_node(identified.uuid)
        assert recovered is not None
        assert recovered.subject_id == _BOB

    @allure.story("Field round-trip")
    @allure.title("KnowledgeNode.subject_id round-trips through the knowledge_nodes DB row converter")
    def test_subject_id_round_trips_through_db_converter(self):
        node = KnowledgeNode(
            text="seen with Bob",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            subject_id=_BOB,
        )
        row = knowledge_node_to_row(node, _GAME_STATE_ID)
        restored = row_to_knowledge_node(row)
        assert restored.subject_id == _BOB

    @allure.story("Field round-trip")
    @allure.title("Anonymous memories serialise to a NULL subject_id row column")
    def test_anonymous_memory_serialises_subject_id_as_null(self):
        node = KnowledgeNode(text="anonymous memory")
        row = knowledge_node_to_row(node, _GAME_STATE_ID)
        assert row["subject_id"] is None
        restored = row_to_knowledge_node(row)
        assert restored.subject_id is None


@allure.epic("Memory & Persistence")
@allure.feature("Identity resolution")
class TestMemoryManagerStampsSubjectId:
    @allure.story("Subject stamping at creation")
    @allure.title("create_memory_from_event stamps subject_id on the shared LOCAL node every witness sees")
    @pytest.mark.asyncio
    async def test_local_event_stamps_subject_id_on_every_witness(self):
        graph = KnowledgeGraph()
        manager = MemoryManager(graph=graph, llm_client=AsyncMock())

        memory_result = await manager.create_memory_from_event(
            MemoryEvent(
                event_description="Bob handed me a coin",
                witness_ids=[_HOLDER_A, _HOLDER_B],
                scope=KnowledgeScope.LOCAL,
                location_id=_FORUM,
                game_time=1.0,
                subject_id=_BOB,
            ),
        )

        # Co-witnesses share one canonical PERSONAL_EXPERIENCE node, so the
        # subject_id must land on that single node and both witnesses must
        # surface the same memory via personal_memories_for.
        assert memory_result.all_ids == (memory_result.canonical_id,)
        canonical = graph.get_node(memory_result.canonical_id)
        assert canonical is not None
        assert canonical.subject_id == _BOB
        for witness_id in (_HOLDER_A, _HOLDER_B):
            assert [mem.uuid for mem in graph.personal_memories_for(witness_id)] == [memory_result.canonical_id]

    @allure.story("Subject stamping at creation")
    @allure.title("create_memory_from_event stamps subject_id on the broadcast node and per-witness copies for CITY")
    @pytest.mark.asyncio
    async def test_broadcast_event_stamps_subject_id_on_every_node(self):
        graph = KnowledgeGraph()
        manager = MemoryManager(graph=graph, llm_client=AsyncMock())

        memory_result = await manager.create_memory_from_event(
            MemoryEvent(
                event_description="Bob shouted at the prefect",
                witness_ids=[_HOLDER_A],
                scope=KnowledgeScope.CITY,
                location_id=_FORUM,
                game_time=1.0,
                subject_id=_BOB,
            ),
        )

        assert len(memory_result.all_ids) == 2
        for node_id in memory_result.all_ids:
            node = graph.get_node(node_id)
            assert node is not None
            assert node.subject_id == _BOB

    @allure.story("Subject stamping at creation")
    @allure.title("Omitting subject_id on the MemoryEvent leaves the resulting nodes anonymous")
    @pytest.mark.asyncio
    async def test_omitting_subject_leaves_nodes_anonymous(self):
        graph = KnowledgeGraph()
        manager = MemoryManager(graph=graph, llm_client=AsyncMock())

        memory_result = await manager.create_memory_from_event(
            MemoryEvent(
                event_description="something happened",
                witness_ids=[_HOLDER_A],
                scope=KnowledgeScope.LOCAL,
                location_id=_FORUM,
                game_time=1.0,
            ),
        )

        assert memory_result.canonical_id is not None
        node = graph.get_node(memory_result.canonical_id)
        assert node is not None
        assert node.subject_id is None

    @allure.story("Subject stamping at creation")
    @allure.title("summarize_interactions_batch stamps subject_id onto the summarised personal memory")
    @pytest.mark.asyncio
    async def test_summarize_batch_stamps_subject_id(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        llm = AsyncMock()
        llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        manager = MemoryManager(graph=graph, llm_client=llm)

        await manager.summarize_interactions_batch(
            [(_HOLDER_A, "player: hi\nMarcus: hail")],
            game_time=2.0,
            subject_id=_BOB,
        )

        memories = graph.personal_memories_for(_HOLDER_A)
        assert len(memories) == 1
        assert memories[0].subject_id == _BOB


@allure.epic("Memory & Persistence")
@allure.feature("Identity resolution")
class TestResolveSubjectIdentity:
    @allure.story("resolve_subject_identity")
    @allure.title("resolve_subject_identity backfills subject_id on holder's matching anonymous memories")
    def test_backfills_matching_anonymous_memories(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        stranger = _attach_memory(graph, _HOLDER_A, _STRANGER_MEMORY, timestamp=1.0)
        unrelated = _attach_memory(graph, _HOLDER_A, _OTHER_MEMORY, timestamp=2.0)

        updated = graph.resolve_subject_identity(
            holder_id=_HOLDER_A,
            subject_id=_BOB,
            predicate=lambda node: "stranger" in node.text,
        )

        assert updated == 1
        assert graph.get_node(stranger.uuid).subject_id == _BOB
        assert graph.get_node(unrelated.uuid).subject_id is None

    @allure.story("resolve_subject_identity")
    @allure.title("resolve_subject_identity refuses to overwrite an existing subject_id")
    def test_refuses_to_overwrite_existing_subject(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        already_named = _attach_memory(
            graph,
            _HOLDER_A,
            _STRANGER_MEMORY,
            timestamp=1.0,
            subject_id=_OTHER,
        )

        updated = graph.resolve_subject_identity(
            holder_id=_HOLDER_A,
            subject_id=_BOB,
            predicate=lambda node: True,
        )

        assert updated == 0
        assert graph.get_node(already_named.uuid).subject_id == _OTHER

    @allure.story("resolve_subject_identity")
    @allure.title("resolve_subject_identity does not touch a different holder's memories")
    def test_scoped_to_holder(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        graph.register_actor_node(_HOLDER_B, label="Cassia")
        marcus_memory = _attach_memory(graph, _HOLDER_A, _STRANGER_MEMORY, timestamp=1.0)
        cassia_memory = _attach_memory(graph, _HOLDER_B, _STRANGER_MEMORY, timestamp=1.0)

        updated = graph.resolve_subject_identity(
            holder_id=_HOLDER_A,
            subject_id=_BOB,
            predicate=lambda node: True,
        )

        assert updated == 1
        assert graph.get_node(marcus_memory.uuid).subject_id == _BOB
        assert graph.get_node(cassia_memory.uuid).subject_id is None

    @allure.story("resolve_subject_identity")
    @allure.title("resolve_subject_identity returns 0 when the holder has no memories")
    def test_zero_when_holder_has_no_memories(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")

        updated = graph.resolve_subject_identity(
            holder_id=_HOLDER_A,
            subject_id=_BOB,
            predicate=lambda node: True,
        )

        assert updated == 0


@allure.epic("Memory & Persistence")
@allure.feature("Identity resolution")
class TestGetMemoriesAboutSubject:
    @allure.story("get_memories_about_subject")
    @allure.title("get_memories_about_subject returns only the holder's memories tagged with the subject")
    def test_returns_only_subject_memories(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        bob_memory = _attach_memory(graph, _HOLDER_A, "Bob smiled", timestamp=1.0, subject_id=_BOB)
        _attach_memory(graph, _HOLDER_A, "the priest spoke", timestamp=2.0, subject_id=_OTHER)
        _attach_memory(graph, _HOLDER_A, "anonymous moment", timestamp=3.0)

        engine = KnowledgeQueryEngine(graph)
        memories = engine.get_memories_about_subject(_HOLDER_A, _BOB)

        assert [memory.uuid for memory in memories] == [bob_memory.uuid]

    @allure.story("get_memories_about_subject")
    @allure.title("get_memories_about_subject does not return another holder's memories about the same subject")
    def test_excludes_other_holders(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        graph.register_actor_node(_HOLDER_B, label="Cassia")
        _attach_memory(graph, _HOLDER_B, "Bob bought wine", timestamp=1.0, subject_id=_BOB)

        engine = KnowledgeQueryEngine(graph)
        assert engine.get_memories_about_subject(_HOLDER_A, _BOB) == []

    @allure.story("get_memories_about_subject")
    @allure.title("After resolve_subject_identity backfills, get_memories_about_subject surfaces the new match")
    def test_resolution_then_query_finds_backfilled_memory(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_HOLDER_A, label="Marcus")
        _attach_memory(graph, _HOLDER_A, _STRANGER_MEMORY, timestamp=1.0)

        engine = KnowledgeQueryEngine(graph)
        assert engine.get_memories_about_subject(_HOLDER_A, _BOB) == []

        graph.resolve_subject_identity(
            holder_id=_HOLDER_A,
            subject_id=_BOB,
            predicate=lambda node: "stranger" in node.text,
        )

        memories = engine.get_memories_about_subject(_HOLDER_A, _BOB)
        assert len(memories) == 1
        assert memories[0].text == _STRANGER_MEMORY


def _stub_item_generator(response: _item_resp.ObjectInteractionResponse) -> _ig_mod.ItemGenerator:
    gen = _ig_mod.ItemGenerator(llm_client=MagicMock())
    gen._send_json = AsyncMock(return_value=response)  # type: ignore[method-assign]
    return gen


@allure.epic("Memory & Persistence")
@allure.feature("Identity resolution")
class TestSubjectStampingConsumerSeams:
    """Reads the persisted node at each wiring site, not just the producer kwarg."""

    @allure.story("Dialogue consumer seam")
    @allure.title("handle_dialogue persists a personal memory whose subject_id is the player's UUID")
    @pytest.mark.asyncio
    async def test_dialogue_summary_subject_is_player(self):
        gs = make_game_state()
        setup_npc(gs, _HOLDER_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_HOLDER_A, label="Marcus (legionary)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[SceneNPC(role="legionary", uuid=_HOLDER_A)],
        )

        actor = make_mock_actor("Hail, traveller.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_HOLDER_A: actor}, memory_manager)

        await handler.handle_dialogue("greetings", ["Marcus"])

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_held_by(_HOLDER_A)
        assert len(memories) == 1
        assert memories[0].subject_id == gs.player.uuid
        assert memories[0].subject_id != _HOLDER_A

    @allure.story("Co-witness consumer seam")
    @allure.title("Co-witness broadcast persists a memory whose subject_id is the player's UUID")
    @pytest.mark.asyncio
    async def test_cowitness_memory_subject_is_player(self):
        gs = make_game_state()
        setup_npc(gs, _HOLDER_A, name="Marcus", occupation="legionary")
        setup_npc(gs, _HOLDER_B, name="Cassia", occupation="innkeeper")
        gs.knowledge_graph.register_actor_node(_HOLDER_A, label="Marcus (legionary)")
        gs.knowledge_graph.register_actor_node(_HOLDER_B, label="Cassia (innkeeper)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[
                SceneNPC(role="legionary", uuid=_HOLDER_A),
                SceneNPC(role="innkeeper", uuid=_HOLDER_B),
            ],
        )

        actor = make_mock_actor("I will report this.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_HOLDER_A: actor}, memory_manager)

        await handler.handle_dialogue("a confession", ["Marcus"])

        cowitness_memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_held_by(_HOLDER_B)
        assert len(cowitness_memories) == 1
        assert cowitness_memories[0].subject_id == gs.player.uuid

    @allure.story("Retaliation consumer seam")
    @allure.title("summarize_retaliations persists a memory whose subject_id is the player's UUID")
    @pytest.mark.asyncio
    async def test_retaliation_memory_subject_is_player(self):
        gs = make_game_state()
        setup_npc(gs, _HOLDER_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_HOLDER_A, label="Marcus (legionary)")

        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body="Marcus recalls the player's insults.", model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {}, memory_manager)

        await handler.summarize_retaliations(
            [{"npc_uuid": _HOLDER_A, "npc_name": "Marcus", "response": "*lunges*"}],
            "shout insults",
        )

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_held_by(_HOLDER_A)
        assert len(memories) == 1
        assert memories[0].subject_id == gs.player.uuid

    @allure.story("Object-interaction consumer seam")
    @allure.title("apply_object_interactions persists a witness memory whose subject_id is the player's UUID")
    @pytest.mark.asyncio
    async def test_object_interaction_witness_subject_is_player(self):
        gs = make_game_state()
        setup_npc(gs, _HOLDER_A, name="Livia", occupation="innkeeper")
        gs.knowledge_graph.register_actor_node(_HOLDER_A, label="Livia (innkeeper)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Rusty Anchor.",
            npcs_present=[SceneNPC(role="innkeeper", uuid=_HOLDER_A)],
        )
        item_gen = _stub_item_generator(
            _item_resp.ObjectInteractionResponse(
                narration="Glass shatters.",
                delta="The front window is broken.",
            ),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=AsyncMock())

        await _doi_mod.apply_object_interactions(
            item_gen,
            ["window"],
            "break the window",
            _doi_mod.ObjectInteractionEnv(gs, memory_manager),
        )

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_held_by(_HOLDER_A)
        assert len(memories) == 1
        assert memories[0].subject_id == gs.player.uuid
