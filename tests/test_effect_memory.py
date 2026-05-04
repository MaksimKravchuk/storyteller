"""Tests for witness memories emitted when EventEffects mutate NPC state.

These exercise the graph-side behaviour added by KER-10. The older
field-level assertions in ``tests/test_effect_applier.py`` cover the
state mutations themselves and are intentionally left untouched.
"""

from __future__ import annotations

from uuid import UUID

import allure

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeScope, KnowledgeSource
from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.setting import Setting
from tests._uuid_helpers import make_uuid
from timeline import effect_applier as _ea, event as _ev, event_manager as _em

EffectApplier = _ea.EffectApplier
EventEffect = _ev.EventEffect
GameEvent = _ev.GameEvent
EventManager = _em.EventManager

_LOC_1 = make_uuid("loc-1")
_LOC_2 = make_uuid("loc-2")


def _make_game_state() -> GameState:
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )


def _register_witness(gs: GameState, witness: NPCCard, location_id: UUID) -> None:
    """Place ``witness`` at ``location_id`` and register their graph node."""
    gs.npcs[witness.uuid] = witness
    gs.locations[location_id].add_npc(witness.uuid)
    gs.knowledge_graph.register_actor_node(witness.uuid, label=witness.name)


def _populate_co_located_pair(
    gs: GameState,
    target: NPCCard,
    witness: NPCCard,
    location_id: UUID,
) -> None:
    """Place ``target`` and ``witness`` in the same location and register the witness."""
    gs.npcs[target.uuid] = target
    gs.locations[location_id] = Location(name="Forum")
    gs.locations[location_id].add_npc(target.uuid)
    _register_witness(gs, witness, location_id)


@allure.epic("Game Timeline")
@allure.feature("Effect-side graph writes")
class TestDeathMemoryPropagation:
    @allure.story("Change status → death")
    @allure.title("CHANGE_STATUS=dead via EventManager creates a witness memory referencing the death")
    def test_scheduled_death_creates_witness_memory(self):
        target = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        witness = NPCCard(name="Livia", occupation="baker", location_id=_LOC_1)
        gs = _make_game_state()
        _populate_co_located_pair(gs, target, witness, _LOC_1)

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

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_held_by(witness.uuid)
        assert memories, "co-located NPC should have witnessed the death"
        assert any("died" in mem.text.lower() for mem in memories)
        assert all(mem.source == KnowledgeSource.PERSONAL_EXPERIENCE for mem in memories)

    @allure.story("Change status → death")
    @allure.title("CHANGE_STATUS=dead also emits a CITY-scope rumor so distant NPCs can learn of it")
    def test_death_emits_city_scope_rumor(self):
        target = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        witness = NPCCard(name="Livia", occupation="baker", location_id=_LOC_1)
        gs = _make_game_state()
        _populate_co_located_pair(gs, target, witness, _LOC_1)

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
            location_id=_LOC_1,
            inventory=["sword"],
        )
        witness = NPCCard(name="Livia", occupation="baker", location_id=_LOC_1)
        gs = _make_game_state()
        _populate_co_located_pair(gs, target, witness, _LOC_1)

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

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_held_by(witness.uuid)
        assert memories, "co-located NPC should have witnessed the item loss"
        assert any("sword" in mem.text.lower() for mem in memories)


@allure.epic("Game Timeline")
@allure.feature("Effect-side graph writes")
class TestMoveNpcMemory:
    @allure.story("Move NPC")
    @allure.title("MOVE_NPC records a departure memory for the NPCs left behind at the origin")
    def test_departure_recorded_for_origin_witnesses(self):
        target = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        witness = NPCCard(name="Livia", occupation="baker", location_id=_LOC_1)
        gs = _make_game_state()
        _populate_co_located_pair(gs, target, witness, _LOC_1)
        gs.locations[_LOC_2] = Location(name="Market")

        EffectApplier(gs, gs.knowledge_graph).apply(
            EventEffect(
                effect_type="MOVE_NPC",
                target_id=target.uuid,
                effect_data={"npc_id": target.uuid, "to_location_id": str(_LOC_2)},
            ),
        )

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_held_by(witness.uuid)
        assert memories, "origin witness should have a departure memory"
        assert any("departed" in mem.text.lower() for mem in memories)


@allure.epic("Game Timeline")
@allure.feature("Effect-side graph writes")
class TestSharedCanonicalWitnessNode:
    """Co-located bystanders must share one ``PERSONAL_EXPERIENCE`` node.

    Locks the sub-linear contract on the EffectApplier's witness
    writer: a single effect with N co-located witnesses adds 1 node
    + N WITNESSED edges, and ``KnowledgeQueryEngine.get_memories_held_by``
    surfaces the same canonical UUID for each witness.
    """

    @allure.story("Co-witness sharing")
    @allure.title("Two co-located witnesses of an effect share one PERSONAL_EXPERIENCE node + 2 WITNESSED edges")
    def test_two_co_witnesses_share_one_personal_node(self):
        target = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        first_witness = NPCCard(name="Livia", occupation="baker", location_id=_LOC_1)
        second_witness = NPCCard(name="Cassia", occupation="bard", location_id=_LOC_1)
        gs = _make_game_state()
        _populate_co_located_pair(gs, target, first_witness, _LOC_1)
        _register_witness(gs, second_witness, _LOC_1)

        EffectApplier(gs, gs.knowledge_graph).apply(
            EventEffect(
                effect_type="ADD_ITEM",
                target_id=target.uuid,
                effect_data={"npc_id": target.uuid, "item": "coin"},
            ),
        )

        engine = KnowledgeQueryEngine(gs.knowledge_graph)
        first_memories = engine.get_memories_held_by(first_witness.uuid)
        second_memories = engine.get_memories_held_by(second_witness.uuid)
        assert len(first_memories) == 1
        assert first_memories[0].source == KnowledgeSource.PERSONAL_EXPERIENCE
        assert [mem.uuid for mem in second_memories] == [first_memories[0].uuid]


@allure.epic("Game Timeline")
@allure.feature("Effect-side graph writes")
class TestMemorySilencing:
    @allure.story("No spurious writes")
    @allure.title("Effects without co-located witnesses emit no LOCAL-scope graph memories")
    def test_no_memory_when_target_is_alone(self):
        target = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        gs = _make_game_state()
        gs.npcs[target.uuid] = target
        gs.locations[_LOC_1] = Location(name="Forum")
        gs.locations[_LOC_1].add_npc(target.uuid)

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
        gs.locations[_LOC_1] = Location(name="Forum")

        EffectApplier(gs, gs.knowledge_graph).apply(
            EventEffect(
                effect_type="ADD_KNOWLEDGE",
                target_id="",
                effect_data={"content": "The bridge has collapsed", "scope": "city"},
            ),
        )

        nodes = gs.knowledge_graph.all_nodes()
        assert len(nodes) == 1
