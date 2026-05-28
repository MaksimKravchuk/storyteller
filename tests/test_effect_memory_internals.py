"""Value-level tests for :mod:`timeline.effect_memory` wording + node writes.

``tests/test_effect_memory.py`` covers graph-write *outcomes*; these pin
the exact wording produced by ``_plan_text`` and the node fields written
by ``write_witness_memories`` — both exercised but never asserted at the
value level, which is where their mutants survived.
"""

from __future__ import annotations

import allure
import pytest

from knowledge.graph import KnowledgeGraph
from knowledge.memory_slots import MemorySlots
from knowledge.node import CanonSource, KnowledgeScope, KnowledgeSource
from tests._uuid_helpers import make_uuid
from timeline.effect_memory import WitnessWrite, _plan_text, write_witness_memories
from timeline.event import EventEffect

_LOC = make_uuid("loc-1")
_WITNESS = make_uuid("npc-witness")
_TARGET = make_uuid("npc-target")
_NAME = "Marcus"
_GAME_TIME = 5.0


def _effect(effect_type: str, **effect_data) -> EventEffect:
    return EventEffect(effect_type=effect_type, target_id=str(_TARGET), effect_data=effect_data)


@allure.epic("Game Timeline")
@allure.feature("Effect memory wording")
class TestPlanTextExactWording:
    @allure.story("Memory wording")
    @allure.title("_plan_text renders the exact witness sentence for each effect type")
    @pytest.mark.parametrize(
        ("effect", "expected"),
        [
            (_effect("ADD_ITEM", item="ring"), "Marcus acquired ring"),
            (_effect("REMOVE_ITEM", item="ring"), "Marcus lost ring"),
            (_effect("CHANGE_ATTRIBUTE", attribute="mood"), "Marcus's mood changed"),
            (_effect("CHANGE_STATUS", status="dead"), "Marcus died"),
            (_effect("CHANGE_STATUS", status="wounded"), "Marcus's condition changed to wounded"),
            (_effect("MOVE_NPC", to_location_id="loc-X"), "Marcus departed for loc-X"),
            (_effect("MOVE_NPC"), "Marcus departed"),
            (_effect("REMOVE_NPC"), "Marcus is no longer here"),
        ],
    )
    def test_exact_text_per_effect(self, effect: EventEffect, expected: str):
        assert _plan_text(effect, _NAME) == expected

    @allure.story("Memory wording")
    @allure.title("_plan_text returns None for effect types and states that produce no memory")
    @pytest.mark.parametrize(
        "effect",
        [
            _effect("ADD_ITEM", item=""),
            _effect("ADD_ITEM"),
            _effect("REMOVE_ITEM", item=""),
            _effect("CHANGE_ATTRIBUTE"),
            _effect("CHANGE_STATUS", status=""),
            _effect("CHANGE_STATUS"),
            _effect("ADD_KNOWLEDGE", content="x"),
            _effect("SPAWN_NPC"),
        ],
    )
    def test_returns_none_when_no_memory(self, effect: EventEffect):
        assert _plan_text(effect, _NAME) is None

    @allure.story("Memory wording")
    @allure.title("_plan_text interpolates the supplied name rather than a placeholder")
    def test_name_is_interpolated(self):
        assert _plan_text(_effect("REMOVE_NPC"), "Livia") == "Livia is no longer here"


@allure.epic("Game Timeline")
@allure.feature("Effect memory wording")
class TestWriteWitnessMemories:
    @allure.story("Node fields")
    @allure.title("A CITY-scope write emits a wider RUMOR node and a shared personal node, both fully populated")
    def test_city_write_populates_both_nodes(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_WITNESS, label="Livia")
        write = WitnessWrite(
            text="Marcus died",
            witness_ids=[_WITNESS],
            scope=KnowledgeScope.CITY,
            location_id=_LOC,
            game_time=_GAME_TIME,
            slots=MemorySlots(subject="Marcus", action="died", outcome="dead"),
        )

        write_witness_memories(graph, write)

        wider = [node for node in graph.all_nodes() if node.scope == KnowledgeScope.CITY]
        personal = [node for node in graph.all_nodes() if node.source == KnowledgeSource.PERSONAL_EXPERIENCE]
        assert len(wider) == 1
        assert len(personal) == 1
        for node in (wider[0], personal[0]):
            assert node.text == "Marcus died"
            assert node.canon == CanonSource.SESSION
            assert node.location_id == _LOC
            assert node.timestamp == _GAME_TIME
            assert node.subject == "Marcus"  # **slot_fields must reach the node
            assert node.action == "died"
        assert wider[0].source == KnowledgeSource.RUMOR
        assert personal[0].scope == KnowledgeScope.LOCAL

    @allure.story("Node fields")
    @allure.title("A COUNTRY-scope write upgrades the wider node from RUMOR to FACT")
    def test_country_scope_writes_fact(self):
        # Pins the `scope >= COUNTRY` boundary: COUNTRY → FACT, anything narrower → RUMOR.
        graph = KnowledgeGraph()
        write = WitnessWrite(
            text="The legate fell",
            witness_ids=[],
            scope=KnowledgeScope.COUNTRY,
            location_id=_LOC,
            game_time=_GAME_TIME,
        )

        write_witness_memories(graph, write)

        wider = graph.all_nodes()
        assert len(wider) == 1
        assert wider[0].source == KnowledgeSource.FACT

    @allure.story("Node fields")
    @allure.title("A REGION-scope write stays a RUMOR (below the COUNTRY FACT threshold)")
    def test_region_scope_stays_rumor(self):
        graph = KnowledgeGraph()
        write = WitnessWrite(
            text="A skirmish in the hills",
            witness_ids=[],
            scope=KnowledgeScope.REGION,
            location_id=_LOC,
            game_time=_GAME_TIME,
        )

        write_witness_memories(graph, write)

        assert graph.all_nodes()[0].source == KnowledgeSource.RUMOR
