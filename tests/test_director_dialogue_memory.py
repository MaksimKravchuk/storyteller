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
_RETALIATION_SUMMARY = "Marcus recalls the player shouting insults and striking back."


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

    @allure.story("Memory summarisation hook")
    @allure.title(
        "summarize_retaliations writes a queryable [retaliation]-tagged memory for the retaliating NPC (KER-12)"
    )
    @pytest.mark.asyncio
    async def test_summarize_retaliations_creates_queryable_memory(self):
        """Regression for KER-12.

        Without this pass, ``check_retaliation`` fires an Actor call for a
        bystander NPC whose mood flipped, appends the response to the
        turn's dialogue output, and moves on — no graph memory is created.
        On the next encounter ``get_memories_about(retaliator)`` returns
        nothing about the fight. This test wires the new
        ``DialogueHandler.summarize_retaliations`` to a real
        ``MemoryManager`` and asserts both (a) the memory exists in the
        graph and (b) the summariser saw a ``[retaliation]``-prefixed log
        so downstream prompts can distinguish provoked combat from
        targeted combat.
        """
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")

        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_RETALIATION_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {}, memory_manager)

        retaliation_entries = [
            {
                "npc_uuid": _NPC_A,
                "npc_name": "Marcus",
                "response": "*lunges at you, sword drawn*",
                "is_retaliation": "true",
            },
        ]

        await handler.summarize_retaliations(retaliation_entries, "shout insults at the legionary")

        engine = KnowledgeQueryEngine(gs.knowledge_graph)
        memories = engine.get_memories_about(_NPC_A)
        assert len(memories) == 1
        assert memories[0].text == _RETALIATION_SUMMARY
        memory_llm.send_message.assert_awaited_once()
        await_args = memory_llm.send_message.await_args
        sent_messages = await_args.kwargs["messages"]
        sent_prompt = sent_messages[0].body
        assert "[retaliation]" in sent_prompt
        assert "shout insults" in sent_prompt
        assert "*lunges at you, sword drawn*" in sent_prompt

    @allure.story("Memory summarisation hook")
    @allure.title("summarize_retaliations skips entries missing an npc_uuid without hitting the summariser")
    @pytest.mark.asyncio
    async def test_summarize_retaliations_skips_entries_without_uuid(self):
        gs = make_game_state()
        memory_manager = AsyncMock(spec=MemoryManager)
        handler = DialogueHandler(gs, {}, memory_manager)

        await handler.summarize_retaliations([], "shout")
        await handler.summarize_retaliations([{"npc_name": "Ghost", "response": "..."}], "shout")

        memory_manager.summarize_interactions_batch.assert_awaited()
        # Both calls must feed an empty pair list — there are no retaliators with a uuid.
        for call in memory_manager.summarize_interactions_batch.await_args_list:
            assert call.args[0] == []


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
