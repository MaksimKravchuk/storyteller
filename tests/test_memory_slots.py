"""Tests for structured memory slots.

Slots (subject/object/action/outcome) are *consumer-seam* metadata: a
unit test that asserts ``node_mod.KnowledgeNode(subject=...)`` round-trips would
not catch the regression that bit past PRs (a field that reaches the
node constructor in unit tests but never makes it onto the per-witness
node the rest of the engine queries). Each test below pins a concrete
production caller — combat, dialogue summariser, co-witness broadcast,
remote events, and effect-driven memories — and asserts the produced
node carries the expected slots.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from typing import Any

from cast import (
    _npc_combat_memory as combat_mod,
    _npc_outcome,
    director_dialogue as dlg_mod,
    director_dialogue_helpers as dlg_helpers,
    director_dialogue_witness as cowitness_mod,
    director_events as events_mod,
    director_object_witness as obj_witness_mod,
)
from db.converters import knowledge as kn_conv
from knowledge import (
    graph as kg_mod,
    memory as mem_mod,
    memory_slots as slots_mod,
    node as node_mod,
)
from llm.message import LLMResponse
from models.npc_card import NPCCard
from tests import _slots_helpers as helpers
from timeline import (
    effect_memory as effect_mod,
    effect_memory_slots as effect_slots_mod,
    event as event_mod,
    event_manager as ev_mgr_mod,
)


# ---------------------------------------------------------------------------
# KnowledgeNode model — slot defaults
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestKnowledgeNodeSlotDefaults:
    @allure.story("Model defaults")
    @allure.title("KnowledgeNode defaults all four structured slots to None")
    def test_slots_default_to_none(self) -> None:
        node = node_mod.KnowledgeNode(text="anything")
        assert node.subject is None
        assert node.object is None
        assert node.action is None
        assert node.outcome is None

    @allure.story("Model defaults")
    @allure.title("KnowledgeNode accepts subject/object/action/outcome on init")
    def test_slots_settable_on_init(self) -> None:
        node = node_mod.KnowledgeNode(
            text="Brutus killed Marcus",
            subject="Brutus",
            object="Marcus",
            action="killed",
            outcome="dead",
        )
        assert node.subject == "Brutus"
        assert node.object == "Marcus"
        assert node.action == "killed"
        assert node.outcome == "dead"


# ---------------------------------------------------------------------------
# DB converter — slots round-trip
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestKnowledgeConverterSlotRoundTrip:
    @allure.story("DB round-trip")
    @allure.title("knowledge_node_to_row preserves all four slots, and row_to_knowledge_node restores them")
    def test_round_trip_preserves_slots(self) -> None:
        node = node_mod.KnowledgeNode(
            text="Brutus killed Marcus",
            subject="Brutus",
            object="Marcus",
            action="killed",
            outcome="dead",
        )
        row = kn_conv.knowledge_node_to_row(node, "gs-1")
        assert row["subject"] == "Brutus"
        assert row["object"] == "Marcus"
        assert row["action"] == "killed"
        assert row["outcome"] == "dead"

        restored = kn_conv.row_to_knowledge_node(row)
        assert restored.subject == "Brutus"
        assert restored.object == "Marcus"
        assert restored.action == "killed"
        assert restored.outcome == "dead"

    @allure.story("Backwards compatibility")
    @allure.title("row_to_knowledge_node defaults slots to None on legacy rows missing the columns")
    def test_legacy_row_defaults_slots_to_none(self) -> None:
        node = node_mod.KnowledgeNode(text="legacy fact")
        row = kn_conv.knowledge_node_to_row(node, "gs-1")
        for key in ("subject", "object", "action", "outcome"):
            row.pop(key)

        restored = kn_conv.row_to_knowledge_node(row)
        assert restored.subject is None
        assert restored.object is None
        assert restored.action is None
        assert restored.outcome is None


# ---------------------------------------------------------------------------
# Consumer seam: combat memory
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestCombatMemorySlotsAtConsumerSeam:
    @allure.story("Combat slots")
    @allure.title("persist_combat_memory writes a node carrying subject=attacker, object=target, action=killed")
    @pytest.mark.asyncio
    async def test_lethal_combat_writes_killed_action_slot(self) -> None:
        state, actor, target = helpers.make_combat_state()
        graph = state.knowledge_graph
        manager = mem_mod.MemoryManager(graph=graph, llm_client=AsyncMock())

        event = combat_mod.CombatEvent(
            actor=actor,
            target=target,
            new_value="dead",
            kind=_npc_outcome.OutcomeKind.PHYSICAL,
        )
        await combat_mod.persist_combat_memory(manager, event, state)

        nodes = [n for n in graph.all_nodes() if n.source == node_mod.KnowledgeSource.PERSONAL_EXPERIENCE]
        assert nodes, "combat memory must produce at least one personal-experience node"
        for node in nodes:
            assert node.subject == "Brutus"
            assert node.object == "Marcus"
            assert node.action == "killed"
            assert node.outcome == "dead"

    @allure.story("Combat slots")
    @allure.title("Non-lethal physical combat writes action=attacked, outcome=wounded")
    @pytest.mark.asyncio
    async def test_wounded_combat_writes_attacked_action_slot(self) -> None:
        state, actor, target = helpers.make_combat_state()
        manager = mem_mod.MemoryManager(graph=state.knowledge_graph, llm_client=AsyncMock())

        event = combat_mod.CombatEvent(
            actor=actor,
            target=target,
            new_value="wounded",
            kind=_npc_outcome.OutcomeKind.PHYSICAL,
        )
        await combat_mod.persist_combat_memory(manager, event, state)

        nodes = [n for n in state.knowledge_graph.all_nodes() if n.action == "attacked"]
        assert nodes
        assert all(node.outcome == "wounded" for node in nodes)

    @allure.story("Combat slots")
    @allure.title("Mood-based intimidation writes action=intimidated, outcome=frightened")
    @pytest.mark.asyncio
    async def test_intimidation_writes_intimidated_action_slot(self) -> None:
        state, actor, target = helpers.make_combat_state()
        manager = mem_mod.MemoryManager(graph=state.knowledge_graph, llm_client=AsyncMock())

        event = combat_mod.CombatEvent(
            actor=actor,
            target=target,
            new_value="frightened",
            kind=_npc_outcome.OutcomeKind.MOOD,
        )
        await combat_mod.persist_combat_memory(manager, event, state)

        nodes = [n for n in state.knowledge_graph.all_nodes() if n.action == "intimidated"]
        assert nodes
        assert all(node.outcome == "frightened" for node in nodes)


# ---------------------------------------------------------------------------
# Consumer seam: dialogue summariser pairs carry slots
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestDialogueSummaryPairCarriesSlots:
    @allure.story("Dialogue slots")
    @allure.title("format_dialogue_summary_pairs sets subject=NPC name, object=player name, action=said")
    def test_pairs_include_speaker_listener_action(self) -> None:
        npc = NPCCard(name="Marcus", occupation="merchant")
        npc.uuid = helpers.MARCUS
        work_items: list[tuple[Any, Any, str, Any, Any]] = [(npc, object(), "Player: hello\n", None, None)]
        entries = [{"npc_name": "Marcus", "response": "Hail, traveller."}]

        pairs = dlg_helpers.format_dialogue_summary_pairs(
            work_items,
            entries,
            "hello",
            player_name=helpers.PLAYER_NAME,
        )

        assert len(pairs) == 1
        pair = pairs[0]
        assert len(pair) == 3, "format_dialogue_summary_pairs must produce slot-bearing 3-tuples"
        slots = pair[2]
        assert slots.subject == "Marcus"
        assert slots.object == helpers.PLAYER_NAME
        assert slots.action == "said"


# ---------------------------------------------------------------------------
# Consumer seam: dialogue summariser writes slots onto produced node
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestSummariserWritesSlotsOntoNode:
    @allure.story("Summariser slots")
    @allure.title("summarize_interactions_batch carries DialoguePair.slots through to the produced KnowledgeNode")
    @pytest.mark.asyncio
    async def test_summariser_threads_slots_to_node(self) -> None:
        graph = kg_mod.KnowledgeGraph()
        llm = AsyncMock()
        llm.send_message = AsyncMock(return_value=LLMResponse(body="summary text", model="stub", usage={}))
        manager = mem_mod.MemoryManager(graph=graph, llm_client=llm)

        graph.register_actor_node(helpers.MARCUS, label="Marcus")
        slots = slots_mod.MemorySlots(subject="Marcus", object=helpers.PLAYER_NAME, action="said")
        await manager.summarize_interactions_batch(
            [(helpers.MARCUS, "Player: hi\nMarcus: hail", slots)],
        )

        produced = [n for n in graph.all_nodes() if n.text == "summary text"]
        assert produced, "summariser must persist the LLM response as a node"
        for node in produced:
            assert node.subject == "Marcus"
            assert node.object == helpers.PLAYER_NAME
            assert node.action == "said"


# ---------------------------------------------------------------------------
# Consumer seam: co-witness overheard memory
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestCowitnessSlotsAtConsumerSeam:
    @allure.story("Overheard slots")
    @allure.title("broadcast_cowitness_memories writes node with subject=player, object=targeted, action=said")
    @pytest.mark.asyncio
    async def test_cowitness_node_carries_speech_slots(self) -> None:
        state = helpers.make_cowitness_state()
        marcus = state.npcs[helpers.MARCUS]
        manager = mem_mod.MemoryManager(graph=state.knowledge_graph, llm_client=AsyncMock())

        work_items: list[tuple[Any, Any, str, Any, Any]] = [(marcus, object(), "Player: hello\n", None, None)]
        entries = [{"npc_name": "Marcus", "response": "Hail."}]

        await cowitness_mod.broadcast_cowitness_memories(work_items, entries, "hello", state, manager)

        # Livia is the only co-witness (Marcus is the target). She should carry an overheard memory
        # tagged with subject=player, object="Marcus", action="said".
        livia_memories = [
            n
            for n in state.knowledge_graph.all_nodes()
            if n.source == node_mod.KnowledgeSource.PERSONAL_EXPERIENCE and n.subject == helpers.PLAYER_NAME
        ]
        assert livia_memories, "co-witness memory must carry slots"
        for node in livia_memories:
            assert node.object == "Marcus"
            assert node.action == "said"


# ---------------------------------------------------------------------------
# Consumer seam: remote events
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestEventProcessorSlots:
    @allure.story("Event slots")
    @allure.title("EventProcessor.build_memory_event threads name → action and description → outcome")
    def test_event_slots_carry_name_and_description(self) -> None:
        state = helpers.make_event_state()
        event_mgr = ev_mgr_mod.EventManager(state, state.knowledge_graph)
        memory_mgr = AsyncMock()
        memory_mgr.create_memory_from_event = AsyncMock(
            return_value=mem_mod.MemoryEventResult(canonical_id=None, all_ids=()),
        )
        processor = events_mod.EventProcessor(state, event_mgr, memory_mgr)

        ev = event_mod.GameEvent(
            name="Riot",
            scheduled_at=0,
            duration=1,
            on_complete_description="A riot breaks out.",
        )

        memory_event = processor.build_memory_event(ev)

        assert memory_event.slots.action == "Riot"
        assert memory_event.slots.outcome == "A riot breaks out."
        # subject is intentionally None — scheduled events have no actor
        assert memory_event.slots.subject is None


# ---------------------------------------------------------------------------
# Consumer seam: effect-driven witness memories
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestEffectMemorySlotsAtConsumerSeam:
    @allure.story("Effect slots")
    @allure.title("CHANGE_STATUS=dead writes subject=NPC, action=died, outcome=dead onto every witness memory")
    def test_change_status_dead_carries_died_action(self) -> None:
        state, pre = helpers.state_with_target_at(helpers.LOC, helpers.MARCUS, "Marcus")
        effect = event_mod.EventEffect(
            effect_type="CHANGE_STATUS",
            target_id=str(helpers.MARCUS),
            effect_data={"status": "dead"},
        )

        effect_mod.emit_memory(state, state.knowledge_graph, effect, pre)

        nodes = [n for n in state.knowledge_graph.all_nodes() if n.subject == "Marcus"]
        assert nodes
        for node in nodes:
            assert node.action == "died"
            assert node.outcome == "dead"

    @allure.story("Effect slots")
    @allure.title("ADD_ITEM writes subject=NPC, action=acquired, object=item")
    def test_add_item_carries_acquired_slots(self) -> None:
        state, pre = helpers.state_with_target_at(helpers.LOC, helpers.MARCUS, "Marcus")
        effect = event_mod.EventEffect(
            effect_type="ADD_ITEM",
            target_id=str(helpers.MARCUS),
            effect_data={"item": "ring"},
        )

        effect_mod.emit_memory(state, state.knowledge_graph, effect, pre)

        nodes = [n for n in state.knowledge_graph.all_nodes() if n.action == "acquired"]
        assert nodes
        for node in nodes:
            assert node.subject == "Marcus"
            assert node.object == "ring"

    @allure.story("Effect slots")
    @allure.title("REMOVE_ITEM, MOVE_NPC, CHANGE_ATTRIBUTE, REMOVE_NPC, and unknown all map to the right verb")
    @pytest.mark.parametrize(
        ("etype", "edata", "expected_action", "expected_object", "expected_outcome"),
        [
            ("REMOVE_ITEM", {"item": "ring"}, "lost", "ring", None),
            ("MOVE_NPC", {"to_location_id": "loc-X"}, "departed", None, "loc-X"),
            ("CHANGE_ATTRIBUTE", {"attribute": "mood"}, "changed_attribute", "mood", None),
            ("REMOVE_NPC", {}, "left_scene", None, None),
            ("CHANGE_STATUS", {"status": "wounded"}, "changed_status", None, "wounded"),
        ],
    )
    def test_each_effect_verb_lands_on_node(
        self,
        etype: str,
        edata: dict,
        expected_action: str,
        expected_object: str | None,
        expected_outcome: str | None,
    ) -> None:
        state, pre = helpers.state_with_target_at(helpers.LOC, helpers.MARCUS, "Marcus")
        effect = event_mod.EventEffect(
            effect_type=etype,
            target_id=str(helpers.MARCUS),
            effect_data=edata,
        )

        effect_mod.emit_memory(state, state.knowledge_graph, effect, pre)

        nodes = [n for n in state.knowledge_graph.all_nodes() if n.subject == "Marcus"]
        assert nodes, "every effect type with a known target must produce at least one witness memory"
        for node in nodes:
            assert node.action == expected_action
            assert node.object == expected_object
            assert node.outcome == expected_outcome


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestUnknownEffectFallsBackToEmptySlots:
    @allure.story("Effect slots")
    @allure.title("Unknown effect_type falls back to EMPTY_SLOTS via slots_for_effect")
    def test_unknown_effect_returns_empty_slots(self) -> None:
        effect = event_mod.EventEffect(effect_type="GRANT_ANCIENT_BLESSING", target_id="x", effect_data={})

        derived = effect_slots_mod.slots_for_effect(effect, "Marcus")

        assert derived == slots_mod.EMPTY_SLOTS


# ---------------------------------------------------------------------------
# Consumer seam: object-interaction witness memories
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestObjectInteractionSlotsAtConsumerSeam:
    @allure.story("Object-interaction slots")
    @allure.title("apply_object_interactions writes subject=player, action=interacted_with onto every witness node")
    @pytest.mark.asyncio
    async def test_object_interaction_carries_player_subject(self) -> None:
        state = helpers.make_cowitness_state()
        manager = mem_mod.MemoryManager(graph=state.knowledge_graph, llm_client=AsyncMock())
        witnesses = [helpers.MARCUS, helpers.LIVIA]

        await obj_witness_mod.emit_witness_memories(manager, state, witnesses, "the window is now shattered")

        nodes = [n for n in state.knowledge_graph.all_nodes() if n.subject == helpers.PLAYER_NAME]
        assert nodes, "object-interaction broadcast must produce witness memories carrying slots"
        for node in nodes:
            assert node.action == "interacted_with"


# ---------------------------------------------------------------------------
# Consumer seam: retaliation memory summariser
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestRetaliationSlotsAtConsumerSeam:
    @allure.story("Retaliation slots")
    @allure.title("summarize_retaliations carries subject=NPC, object=player, action=retaliated_against to the node")
    @pytest.mark.asyncio
    async def test_retaliation_node_carries_slots(self) -> None:
        state = helpers.make_cowitness_state()
        state.knowledge_graph.register_actor_node(helpers.MARCUS, label="Marcus")
        llm = AsyncMock()
        llm.send_message = AsyncMock(return_value=LLMResponse(body="Marcus retaliated.", model="stub", usage={}))
        manager = mem_mod.MemoryManager(graph=state.knowledge_graph, llm_client=llm)

        handler = dlg_mod.DialogueHandler(state, {}, manager)
        retaliation_entries: list[dict[str, Any]] = [
            {"npc_uuid": helpers.MARCUS, "npc_name": "Marcus", "response": "*lunges*"},
        ]

        await handler.summarize_retaliations(retaliation_entries, "shout insults")

        retaliated_nodes = [n for n in state.knowledge_graph.all_nodes() if n.action == "retaliated_against"]
        assert retaliated_nodes
        for node in retaliated_nodes:
            assert node.subject == "Marcus"
            assert node.object == helpers.PLAYER_NAME


# ---------------------------------------------------------------------------
# Default behaviour — empty slots produce all-None on the node
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestEmptySlotsLeaveNodeFieldsNone:
    @allure.story("Empty slots")
    @allure.title("create_memory_from_event without slots leaves every slot field None on the produced node")
    @pytest.mark.asyncio
    async def test_empty_slots_default_to_none(self) -> None:
        graph = kg_mod.KnowledgeGraph()
        llm = AsyncMock()
        llm.send_message = AsyncMock(return_value=LLMResponse(body="x", model="stub", usage={}))
        manager = mem_mod.MemoryManager(graph=graph, llm_client=llm)

        result = await manager.create_memory_from_event(
            mem_mod.MemoryEvent(
                event_description="bare event",
                witness_ids=[helpers.BRUTUS],
                scope=node_mod.KnowledgeScope.LOCAL,
                slots=slots_mod.EMPTY_SLOTS,
            ),
        )

        assert result.canonical_id is not None
        node = graph.get_node(result.canonical_id)
        assert node is not None
        assert node.subject is None
        assert node.object is None
        assert node.action is None
        assert node.outcome is None


# ---------------------------------------------------------------------------
# MemorySlots dataclass surface
# ---------------------------------------------------------------------------


@allure.epic("Memory & Persistence")
@allure.feature("Structured memory slots")
class TestMemorySlotsDataclass:
    @allure.story("Slot defaults")
    @allure.title("EMPTY_SLOTS has every field set to None")
    def test_empty_slots_all_none(self) -> None:
        assert slots_mod.EMPTY_SLOTS.subject is None
        assert slots_mod.EMPTY_SLOTS.object is None
        assert slots_mod.EMPTY_SLOTS.action is None
        assert slots_mod.EMPTY_SLOTS.outcome is None

    @allure.story("Frozen dataclass")
    @allure.title("MemorySlots is frozen — fields cannot be mutated post-construction")
    def test_slots_are_frozen(self) -> None:
        slots = slots_mod.MemorySlots(subject="x")
        with pytest.raises(AttributeError):
            slots.subject = "y"  # type: ignore[misc]
