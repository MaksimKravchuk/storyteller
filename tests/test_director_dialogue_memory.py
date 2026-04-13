"""Director long-term memory tests — DialogueHandler + NPC graph registration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.director_dialogue import DialogueHandler
from knowledge.memory import MemoryManager
from knowledge.query import KnowledgeQueryEngine
from llm.message import LLMResponse
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from tests.director_helpers import make_director, make_game_state, make_mock_agent, setup_npc

_NPC_A = "npc-1"
_MEMORY_SUMMARY = "Marcus finds the player curious and welcoming."


@allure.epic("Memory & Persistence")
@allure.feature("Dialogue routing")
class TestDialogueHandlerLongTermMemory:
    """After a TALK turn, participating NPCs get queryable long-term memories."""

    @allure.story("Memory summarisation hook")
    @allure.title("handle_dialogue summarises the exchange into a queryable memory for each participating NPC")
    @pytest.mark.asyncio
    async def test_handle_dialogue_creates_queryable_memory(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")
        gs.current_scene = Scene(
            location_id="forum",
            description="The Forum.",
            npcs_present=[SceneNPC(role="legionary", uuid=_NPC_A)],
        )

        actor = make_mock_agent("Hail, traveller.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_NPC_A: actor}, memory_manager)

        await handler.handle_dialogue("greetings", ["Marcus"])

        engine = KnowledgeQueryEngine(gs.knowledge_graph)
        memories = engine.get_memories_about(_NPC_A)
        assert len(memories) == 1
        assert memories[0].text == _MEMORY_SUMMARY
        memory_llm.send_message.assert_awaited_once()

    @allure.story("Memory summarisation hook")
    @allure.title("handle_dialogue does not call the memory manager when no NPC work items are resolved")
    @pytest.mark.asyncio
    async def test_handle_dialogue_no_summary_when_no_targets(self):
        gs = make_game_state()
        memory_manager = AsyncMock(spec=MemoryManager)
        handler = DialogueHandler(gs, {}, memory_manager)

        dialogue_entries, combat_engaged = await handler.handle_dialogue("look around", ["stranger"])

        assert dialogue_entries == []
        assert combat_engaged == set()
        memory_manager.summarize_interaction.assert_not_called()


@allure.epic("NPC Interaction")
@allure.feature("Director registration")
class TestDirectorRegistersNpcGraphNode:
    @allure.story("NPC graph registration")
    @allure.title("_register_new_npc adds the NPC uuid as a node to the knowledge graph")
    def test_register_new_npc_adds_graph_node(self):
        gs = make_game_state()
        director = make_director(game_state=gs)
        npc = NPCCard(name="Blacksmith", occupation="smith")
        npc.uuid = "smith-1"

        director._register_new_npc(npc)

        assert "smith-1" in gs.knowledge_graph.digraph.nodes
        # Actor is registered and can be looked up.
        assert "smith-1" in director._actors
