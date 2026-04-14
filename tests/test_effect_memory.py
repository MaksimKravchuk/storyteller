"""Tests for witness memories emitted when EventEffects mutate NPC state.

These exercise the graph-side behaviour added by KER-10. The older
field-level assertions in ``tests/test_effect_applier.py`` cover the
state mutations themselves and are intentionally left untouched.
"""

from __future__ import annotations

import allure

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeScope, KnowledgeSource
from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.setting import Setting
from timeline.effect_applier import EffectApplier
from timeline.event import EventEffect, GameEvent
from timeline.event_manager import EventManager


def _make_game_state() -> GameState:
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )


def _populate_co_located_pair(
    gs: GameState,
    target: NPCCard,
    witness: NPCCard,
    location_id: str,
) -> None:
    """Place ``target`` and ``witness`` in the same location and register the witness."""
    gs.npcs[target.uuid] = target
    gs.npcs[witness.uuid] = witness
    gs.locations[location_id] = Location(name="Forum")
    gs.locations[location_id].add_npc(target.uuid)
    gs.locations[location_id].add_npc(witness.uuid)
    gs.knowledge_graph.register_actor_node(witness.uuid, label=witness.name)


@allure.epic("Game Timeline")
@allure.feature("Effect-side graph writes")
class TestDeathMemoryPropagation:
    @allure.story("Change status → death")
    @allure.title("CHANGE_STATUS=dead via EventManager creates a witness memory referencing the death")
    def test_scheduled_death_creates_witness_memory(self):
        target = NPCCard(name="Marcus", occupation="guard", location_id="loc-1")
        witness = NPCCard(name="Livia", occupation="baker", location_id="loc-1")
        gs = _make_game_state()
        _populate_co_located_pair(gs, target, witness, "loc-1")

        mgr = EventManager(gs, gs.knowledge_graph)
        mgr.schedule(
            GameEvent(
                name="Guard falls",
                scheduled_at=0,
                duration=1,
                effects=[
                    EventEffect(
                        effect_type="CHANGE_STATUS",
                        target_id=target.uuid,
                        effect_data={"npc_id": target.uuid, "status": "dead"},
                    ),
                ],
            ),
        )
        mgr.advance_time(2.0)

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_about(witness.uuid)
        assert memories, "co-located NPC should have witnessed the death"
        assert any("died" in mem.text.lower() for mem in memories)
        assert all(mem.source == KnowledgeSource.PERSONAL_EXPERIENCE for mem in memories)

    @allure.story("Change status → death")
    @allure.title("CHANGE_STATUS=dead also emits a CITY-scope rumor so distant NPCs can learn of it")
    def test_death_emits_city_scope_rumor(self):
        target = NPCCard(name="Marcus", occupation="guard", location_id="loc-1")
        witness = NPCCard(name="Livia", occupation="baker", location_id="loc-1")
        gs = _make_game_state()
        _populate_co_located_pair(gs, target, witness, "loc-1")

        EffectApplier(gs, gs.knowledge_graph).apply(
            EventEffect(
                effect_type="CHANGE_STATUS",
                target_id=target.uuid,
                effect_data={"npc_id": target.uuid, "status": "dead"},
            ),
        )

        city_rumors = [
            node
            for node in gs.knowledge_graph.all_nodes()
            if node.scope == KnowledgeScope.CITY and node.source == KnowledgeSource.RUMOR
        ]
        assert len(city_rumors) == 1
        assert "died" in city_rumors[0].text.lower()


@allure.epic("Game Timeline")
@allure.feature("Effect-side graph writes")
class TestItemMemoryPropagation:
    @allure.story("Remove item")
    @allure.title("REMOVE_ITEM via EventManager leaves a witness memory referencing the lost item")
    def test_scheduled_item_loss_creates_witness_memory(self):
        target = NPCCard(
            name="Marcus",
            occupation="guard",
            location_id="loc-1",
            inventory=["sword"],
        )
        witness = NPCCard(name="Livia", occupation="baker", location_id="loc-1")
        gs = _make_game_state()
        _populate_co_located_pair(gs, target, witness, "loc-1")

        mgr = EventManager(gs, gs.knowledge_graph)
        mgr.schedule(
            GameEvent(
                name="Theft",
                scheduled_at=0,
                duration=1,
                effects=[
                    EventEffect(
                        effect_type="REMOVE_ITEM",
                        target_id=target.uuid,
                        effect_data={"npc_id": target.uuid, "item": "sword"},
                    ),
                ],
            ),
        )
        mgr.advance_time(2.0)

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_about(witness.uuid)
        assert memories, "co-located NPC should have witnessed the item loss"
        assert any("sword" in mem.text.lower() for mem in memories)


@allure.epic("Game Timeline")
@allure.feature("Effect-side graph writes")
class TestMoveNpcMemory:
    @allure.story("Move NPC")
    @allure.title("MOVE_NPC records a departure memory for the NPCs left behind at the origin")
    def test_departure_recorded_for_origin_witnesses(self):
        target = NPCCard(name="Marcus", occupation="guard", location_id="loc-1")
        witness = NPCCard(name="Livia", occupation="baker", location_id="loc-1")
        gs = _make_game_state()
        _populate_co_located_pair(gs, target, witness, "loc-1")
        gs.locations["loc-2"] = Location(name="Market")

        EffectApplier(gs, gs.knowledge_graph).apply(
            EventEffect(
                effect_type="MOVE_NPC",
                target_id=target.uuid,
                effect_data={"npc_id": target.uuid, "to_location_id": "loc-2"},
            ),
        )

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_about(witness.uuid)
        assert memories, "origin witness should have a departure memory"
        assert any("departed" in mem.text.lower() for mem in memories)


@allure.epic("Game Timeline")
@allure.feature("Effect-side graph writes")
class TestMemorySilencing:
    @allure.story("No spurious writes")
    @allure.title("Effects without co-located witnesses emit no LOCAL-scope graph memories")
    def test_no_memory_when_target_is_alone(self):
        target = NPCCard(name="Marcus", occupation="guard", location_id="loc-1")
        gs = _make_game_state()
        gs.npcs[target.uuid] = target
        gs.locations["loc-1"] = Location(name="Forum")
        gs.locations["loc-1"].add_npc(target.uuid)

        EffectApplier(gs, gs.knowledge_graph).apply(
            EventEffect(
                effect_type="ADD_ITEM",
                target_id=target.uuid,
                effect_data={"npc_id": target.uuid, "item": "coin"},
            ),
        )

        assert gs.knowledge_graph.all_nodes() == []

    @allure.story("No spurious writes")
    @allure.title("ADD_KNOWLEDGE does not double-write a memory (handler already writes the graph node)")
    def test_add_knowledge_is_not_double_written(self):
        gs = _make_game_state()
        gs.locations["loc-1"] = Location(name="Forum")

        EffectApplier(gs, gs.knowledge_graph).apply(
            EventEffect(
                effect_type="ADD_KNOWLEDGE",
                target_id="",
                effect_data={"content": "The bridge has collapsed", "scope": "city"},
            ),
        )

        nodes = gs.knowledge_graph.all_nodes()
        assert len(nodes) == 1
