"""Director long-term memory tests — DialogueHandler + NPC graph registration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.director_dialogue import DialogueHandler
from knowledge import memory as _km, query as _kq, salience as salience_presets
from llm.message import LLMResponse
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from tests._uuid_helpers import make_uuid
from tests.director_helpers import make_director, make_game_state, make_mock_actor, setup_npc

MemoryManager = _km.MemoryManager
KnowledgeQueryEngine = _kq.KnowledgeQueryEngine

_NPC_A = make_uuid("npc-1")
_NPC_B = make_uuid("npc-2")
_FORUM = make_uuid("forum")
_MEMORY_SUMMARY = "Marcus finds the player curious and welcoming."
_RETALIATION_SUMMARY = "Marcus recalls the player shouting insults and striking back."
_DAMNING_STATEMENT = "I killed the duke's son last winter"


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
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[SceneNPC(role="legionary", uuid=_NPC_A)],
        )

        actor = make_mock_actor("Hail, traveller.")
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
        assert memories[0].salience == pytest.approx(salience_presets.ROUTINE_DIALOGUE)
        memory_llm.send_message.assert_awaited_once()

    @allure.story("Co-witness memory broadcast")
    @allure.title(
        "handle_dialogue gives every non-targeted scene NPC an overheard memory referencing the player's statement "
        "(KER-11)",
    )
    @pytest.mark.asyncio
    async def test_handle_dialogue_broadcasts_cowitness_memory(self):
        """Regression for KER-11.

        Before the co-witness broadcast, a player who confessed a crime
        to NPC A while NPC B was standing right next to them would find
        NPC B later had *no memory* of the confession — only NPC A was
        in the dialogue work items, and ``_summarize_interactions`` only
        iterated those. This test wires a two-NPC scene, runs a single
        TALK turn aimed at NPC A, and checks that NPC B's personal
        memories come back carrying the player's incriminating text
        without the summariser having been called a second time for
        the bystander.
        """
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        setup_npc(gs, _NPC_B, name="Cassia", occupation="innkeeper")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")
        gs.knowledge_graph.register_actor_node(_NPC_B, label="Cassia (innkeeper)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[
                SceneNPC(role="legionary", uuid=_NPC_A),
                SceneNPC(role="innkeeper", uuid=_NPC_B),
            ],
        )

        actor_a = make_mock_actor("I will report this to the prefect.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_NPC_A: actor_a}, memory_manager)

        await handler.handle_dialogue(_DAMNING_STATEMENT, ["Marcus"])

        engine = KnowledgeQueryEngine(gs.knowledge_graph)

        # Target NPC got the LLM summary, exactly as before.
        target_memories = engine.get_memories_about(_NPC_A)
        assert len(target_memories) == 1
        assert target_memories[0].text == _MEMORY_SUMMARY

        # Co-witness NPC got a queryable memory whose text references the statement,
        # created without touching the LLM summariser.
        cowitness_memories = engine.get_memories_about(_NPC_B)
        assert len(cowitness_memories) == 1
        assert _DAMNING_STATEMENT in cowitness_memories[0].text
        assert "Marcus" in cowitness_memories[0].text
        assert cowitness_memories[0].salience == pytest.approx(salience_presets.OVERHEARD)

        # The co-witness broadcast also surfaces as a learned fact on the
        # player, so the Character sidebar can render the confession the
        # player just made.
        assert len(gs.player.learned_facts) == 1
        fact_uuid = next(iter(gs.player.learned_facts))
        fact_node = gs.knowledge_graph.get_node(fact_uuid)
        assert fact_node is not None
        assert _DAMNING_STATEMENT in fact_node.text

        # LLM is called exactly once — only for the targeted NPC. Co-witness
        # memories are rendered from the raw transcript and do not issue
        # any extra LLM calls.
        memory_llm.send_message.assert_awaited_once()

    @allure.story("Memory summarisation hook")
    @allure.title(
        "handle_dialogue tags the targeted NPC's dialogue summary memory with the current scene's location_id",
    )
    @pytest.mark.asyncio
    async def test_handle_dialogue_summary_carries_scene_location_id(self):
        """Dialogue summary memories must carry location_id so the location filter applies consistently.

        Regression for the bug where ``_summarize_one`` dropped ``location_id``
        even though sibling memories from ``create_memory_from_event`` set it.
        """
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[SceneNPC(role="legionary", uuid=_NPC_A)],
        )

        actor = make_mock_actor("Hail, traveller.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_NPC_A: actor}, memory_manager)

        await handler.handle_dialogue("greetings", ["Marcus"])

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_about(_NPC_A)
        assert len(memories) == 1
        assert memories[0].location_id == _FORUM

    @allure.story("Co-witness memory broadcast")
    @allure.title(
        "handle_dialogue with only a targeted NPC creates no extra co-witness nodes (KER-11 regression baseline)",
    )
    @pytest.mark.asyncio
    async def test_handle_dialogue_single_target_no_extra_cowitness_nodes(self):
        """Regression baseline for KER-11.

        With the co-witness broadcast in place, a single-NPC scene must
        not gain any stray nodes or edges just because the new pass
        runs — the pre-KER-11 behaviour is preserved exactly.
        """
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[SceneNPC(role="legionary", uuid=_NPC_A)],
        )

        actor = make_mock_actor("Hail, traveller.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_NPC_A: actor}, memory_manager)

        nodes_before = len(gs.knowledge_graph.digraph.nodes)

        await handler.handle_dialogue("greetings", ["Marcus"])

        # Exactly one new node was added: the targeted NPC's LLM summary.
        nodes_after = len(gs.knowledge_graph.digraph.nodes)
        assert nodes_after - nodes_before == 1
        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_about(_NPC_A)
        assert len(memories) == 1
        assert memories[0].text == _MEMORY_SUMMARY

    @allure.story("Co-witness memory broadcast")
    @allure.title("handle_dialogue skips uninitialised scene NPC stubs when broadcasting co-witness memories (KER-11)")
    @pytest.mark.asyncio
    async def test_handle_dialogue_skips_uninitialised_scene_stubs(self):
        """A freshly-minted ``SceneNPC`` stub with no ``uuid`` yet has no
        graph node, so it must not receive a co-witness memory — there
        is no endpoint for the ``WITNESSED`` edge. Only initialised NPCs
        with a registered card are eligible witnesses.
        """
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[
                SceneNPC(role="legionary", uuid=_NPC_A),
                SceneNPC(role="beggar"),  # Uninitialised — must be skipped.
            ],
        )

        actor = make_mock_actor("Hail, traveller.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_NPC_A: actor}, memory_manager)

        nodes_before = len(gs.knowledge_graph.digraph.nodes)
        await handler.handle_dialogue("greetings", ["Marcus"])
        nodes_after = len(gs.knowledge_graph.digraph.nodes)

        # Only the targeted summary node was added — the uninitialised stub
        # is not a witness endpoint.
        assert nodes_after - nodes_before == 1
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
        pairs = memory_manager.summarize_interactions_batch.call_args[0][0]
        assert pairs == []

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
        assert memories[0].salience == pytest.approx(salience_presets.RETALIATION)
        memory_llm.send_message.assert_awaited_once()
        await_args = memory_llm.send_message.await_args
        sent_messages = await_args.kwargs["messages"]
        sent_prompt = sent_messages[0].body
        assert "[retaliation]" in sent_prompt
        assert "shout insults" in sent_prompt
        assert "*lunges at you, sword drawn*" in sent_prompt

    @allure.story("Memory summarisation hook")
    @allure.title("summarize_retaliations tags the retaliating NPC's memory with the current scene's location_id")
    @pytest.mark.asyncio
    async def test_summarize_retaliations_carries_scene_location_id(self):
        """Retaliation summaries must carry location_id like targeted dialogue summaries."""
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[SceneNPC(role="legionary", uuid=_NPC_A)],
        )

        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_RETALIATION_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {}, memory_manager)

        retaliation_entries = [
            {"npc_uuid": _NPC_A, "npc_name": "Marcus", "response": "*lunges*"},
        ]

        await handler.summarize_retaliations(retaliation_entries, "shout insults")

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_about(_NPC_A)
        assert len(memories) == 1
        assert memories[0].location_id == _FORUM

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


@allure.epic("Narrative Delivery")
@allure.feature("Dialogue routing")
class TestDialogueHandlerEntryProduction:
    """``handle_dialogue`` must populate ``DialogueEntry.npc_uuid`` from
    the NPC card. The Narrator gates player-facing names on that uuid;
    a producer that drops it would silently leak proper names while
    every Narrator unit test (which sets uuids directly) keeps passing.
    """

    @allure.story("Producer handoff")
    @allure.title("DialogueHandler.handle_dialogue stamps each entry with the speaker NPC's uuid")
    @pytest.mark.asyncio
    async def test_handle_dialogue_entries_carry_npc_uuid(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[SceneNPC(role="legionary", uuid=_NPC_A)],
        )

        actor = make_mock_actor("Hail, traveller.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_NPC_A: actor}, memory_manager)

        entries, _ = await handler.handle_dialogue("greetings", ["Marcus"])

        assert len(entries) == 1
        assert entries[0]["npc_name"] == "Marcus"
        assert entries[0]["npc_uuid"] == _NPC_A


@allure.epic("Memory & Persistence")
@allure.feature("NPC conversation history")
class TestDialogueHandlerConversationHistory:
    """After a TALK turn, the targeted NPC's ``conversation_history`` grows (KER-37)."""

    @allure.story("Conversation history append")
    @allure.title("handle_dialogue appends one user/assistant pair to a freshly initialised NPC")
    @pytest.mark.asyncio
    async def test_handle_dialogue_appends_player_and_npc_entries(self):
        gs = make_game_state()
        npc = setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[SceneNPC(role="legionary", uuid=_NPC_A)],
        )

        actor = make_mock_actor("Hail, traveller.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_NPC_A: actor}, memory_manager)

        await handler.handle_dialogue("greetings", ["Marcus"])

        assert npc.conversation_history == [
            {"role": "user", "content": "greetings"},
            {"role": "assistant", "content": "Hail, traveller."},
        ]

    @allure.story("Conversation history append")
    @allure.title("handle_dialogue extends a pre-seeded conversation_history without replacing it")
    @pytest.mark.asyncio
    async def test_handle_dialogue_extends_pre_seeded_history(self):
        gs = make_game_state()
        seed = [
            {"role": "user", "content": "Tell me how business is, Marcus."},
            {"role": "assistant", "content": "Terrible, friend."},
        ]
        npc = setup_npc(gs, _NPC_A, name="Marcus", occupation="baker")
        npc.conversation_history = list(seed)
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (baker)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[SceneNPC(role="baker", uuid=_NPC_A)],
        )

        actor = make_mock_actor("Still terrible, friend.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_NPC_A: actor}, memory_manager)

        await handler.handle_dialogue("How is business today?", ["Marcus"])

        assert npc.conversation_history[:2] == seed
        assert npc.conversation_history[2:] == [
            {"role": "user", "content": "How is business today?"},
            {"role": "assistant", "content": "Still terrible, friend."},
        ]

    @allure.story("Conversation history append")
    @allure.title("handle_dialogue appends per NPC independently when multiple targets share a turn")
    @pytest.mark.asyncio
    async def test_handle_dialogue_appends_per_npc_independently(self):
        gs = make_game_state()
        npc_a = setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        npc_b = setup_npc(gs, _NPC_B, name="Cassia", occupation="innkeeper")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")
        gs.knowledge_graph.register_actor_node(_NPC_B, label="Cassia (innkeeper)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[
                SceneNPC(role="legionary", uuid=_NPC_A),
                SceneNPC(role="innkeeper", uuid=_NPC_B),
            ],
        )

        actor_a = make_mock_actor("Marcus speaks.")
        actor_b = make_mock_actor("Cassia speaks.")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_NPC_A: actor_a, _NPC_B: actor_b}, memory_manager)

        await handler.handle_dialogue("hello both", ["Marcus", "Cassia"])

        assert npc_a.conversation_history == [
            {"role": "user", "content": "hello both"},
            {"role": "assistant", "content": "Marcus speaks."},
        ]
        assert npc_b.conversation_history == [
            {"role": "user", "content": "hello both"},
            {"role": "assistant", "content": "Cassia speaks."},
        ]

    @allure.story("Conversation history append")
    @allure.title("handle_dialogue persists the bare player utterance, not the dice-wrapped action_text")
    @pytest.mark.asyncio
    async def test_handle_dialogue_persists_bare_player_action_when_aggressive(self):
        """Pins the design choice from KER-37 — the persisted history records what the
        player *said*, not the contest-decorated prompt the Actor LLM consumes. A
        future refactor that swaps ``player_action`` for the work-item ``action_text``
        would leak ``[DICE ROLL: …]`` blobs into JSONB; this test catches that.
        """
        gs = make_game_state()
        npc = setup_npc(gs, _NPC_A, name="Marcus", occupation="legionary")
        gs.knowledge_graph.register_actor_node(_NPC_A, label="Marcus (legionary)")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[SceneNPC(role="legionary", uuid=_NPC_A)],
        )

        actor = make_mock_actor("*draws sword*")
        memory_llm = AsyncMock()
        memory_llm.send_message = AsyncMock(
            return_value=LLMResponse(body=_MEMORY_SUMMARY, model="stub", usage={}),
        )
        memory_manager = MemoryManager(graph=gs.knowledge_graph, llm_client=memory_llm)
        handler = DialogueHandler(gs, {_NPC_A: actor}, memory_manager)

        await handler.handle_dialogue("shove him", ["Marcus"], is_aggressive=True)

        assert npc.conversation_history == [
            {"role": "user", "content": "shove him"},
            {"role": "assistant", "content": "*draws sword*"},
        ]


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
