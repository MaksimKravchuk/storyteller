"""Scope/guard and pre-state tests for :mod:`timeline.effect_memory`.

Pins ``emit_memory``'s CITY-vs-LOCAL scope choice and witness-guard
early return, plus ``capture_pre_state``'s npc-id resolution — the
decision points whose mutants survived the graph-outcome tests.
"""

from __future__ import annotations

import allure

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeScope
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.setting import Setting
from tests._uuid_helpers import make_uuid
from timeline.effect_memory import EffectPreState, capture_pre_state, emit_memory
from timeline.event import EventEffect

_LOC = make_uuid("loc-1")
_TARGET = make_uuid("npc-target")
_NAME = "Marcus"
_CLOCK = 7.0


def _bare_state() -> GameState:
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )


def _state_with_target_only() -> GameState:
    """Target alone at _LOC — no co-located witnesses."""
    state = _bare_state()
    location = Location(name="Forum")
    location.uuid = _LOC
    location.npcs_present = [_TARGET]
    state.locations[_LOC] = location
    return state


def _effect(effect_type: str, **effect_data) -> EventEffect:
    return EventEffect(effect_type=effect_type, target_id=str(_TARGET), effect_data=effect_data)


def _pre() -> EffectPreState:
    return EffectPreState(npc_id=_TARGET, npc_name=_NAME, location_id=_LOC)


@allure.epic("Game Timeline")
@allure.feature("Effect memory emission")
class TestEmitMemoryScopeAndGuards:
    @allure.story("Death rumor")
    @allure.title("A death with no co-located witness still emits the CITY-scope rumor")
    def test_death_alone_emits_city_rumor(self):
        # Pins `if not witness_ids and scope == LOCAL: return` — death is CITY, so it must NOT return.
        state = _state_with_target_only()
        emit_memory(state, state.knowledge_graph, _effect("CHANGE_STATUS", status="dead"), _pre())

        rumors = [node for node in state.knowledge_graph.all_nodes() if node.scope == KnowledgeScope.CITY]
        assert len(rumors) == 1
        assert rumors[0].text == "Marcus died"

    @allure.story("Local silence")
    @allure.title("A non-fatal status change with no witness emits nothing (LOCAL scope, no listeners)")
    def test_non_fatal_change_alone_is_silent(self):
        # Pins `etype == CHANGE_STATUS and stat == dead` (the `and`): wounded must stay LOCAL → silent.
        state = _state_with_target_only()
        emit_memory(state, state.knowledge_graph, _effect("CHANGE_STATUS", status="wounded"), _pre())

        assert state.knowledge_graph.all_nodes() == []

    @allure.story("Node fields")
    @allure.title("The emitted node carries the pre-state location and the current game clock")
    def test_node_carries_location_and_time(self):
        state = _state_with_target_only()
        state.game_clock = _CLOCK
        emit_memory(state, state.knowledge_graph, _effect("CHANGE_STATUS", status="dead"), _pre())

        rumor = next(node for node in state.knowledge_graph.all_nodes() if node.scope == KnowledgeScope.CITY)
        assert rumor.location_id == _LOC
        assert rumor.timestamp == _CLOCK


@allure.epic("Game Timeline")
@allure.feature("Effect memory pre-state")
class TestCapturePreState:
    @allure.story("NPC resolution")
    @allure.title("capture_pre_state resolves the NPC via the effect_data npc_id, not target_id")
    def test_resolves_via_npc_id_key(self):
        # target_id points at a non-existent NPC; the real NPC lives under the npc_id key.
        state = _bare_state()
        npc = NPCCard(name=_NAME, occupation="guard", location_id=_LOC)
        npc.uuid = _TARGET
        state.npcs[_TARGET] = npc
        effect = EventEffect(
            effect_type="CHANGE_STATUS",
            target_id=str(make_uuid("nonexistent")),
            effect_data={"npc_id": str(_TARGET), "status": "dead"},
        )

        pre = capture_pre_state(state, effect)

        assert pre.npc_id == _TARGET
        assert pre.npc_name == _NAME
        assert pre.location_id == _LOC

    @allure.story("NPC resolution")
    @allure.title("capture_pre_state returns an empty pre-state when the NPC cannot be found")
    def test_empty_when_npc_missing(self):
        pre = capture_pre_state(_bare_state(), _effect("CHANGE_STATUS", status="dead"))
        assert pre.npc_id is None
