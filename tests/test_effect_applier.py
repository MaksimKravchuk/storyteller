"""Tests for EffectApplier — CHANGE_STATUS effect type."""

from __future__ import annotations

import allure

from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.npc_card import NPCCard
from models.setting import Setting
from timeline.effect_applier import EffectApplier
from timeline.event import EventEffect


def _make_game_state_with_npc(npc: NPCCard) -> GameState:
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    gs.npcs[npc.uuid] = npc
    return gs


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestChangeStatusEffect:
    @allure.story("Change status")
    @allure.title("CHANGE_STATUS effect updates the target NPC's physical_status field in place")
    def test_changes_physical_status(self):
        npc = NPCCard(name="Guard", occupation="guard", physical_status="wounded")
        gs = _make_game_state_with_npc(npc)
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type="CHANGE_STATUS",
            target_id=npc.uuid,
            effect_data={"npc_id": npc.uuid, "status": "healthy"},
        )
        applier.apply(effect)
        assert npc.physical_status == "healthy"

    @allure.story("No-op on missing target")
    @allure.title("CHANGE_STATUS effect targeting an unknown NPC UUID is silently ignored without raising")
    def test_noop_when_npc_not_found(self):
        npc = NPCCard(name="Guard", occupation="guard")
        gs = _make_game_state_with_npc(npc)
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type="CHANGE_STATUS",
            target_id="nonexistent-uuid",
            effect_data={"npc_id": "nonexistent-uuid", "status": "wounded"},
        )
        # Should not raise
        applier.apply(effect)
        assert npc.physical_status == "healthy"

    @allure.story("Change status")
    @allure.title("CHANGE_STATUS effect accepts free-form multi-word status strings like 'wounded left arm'")
    def test_sets_multi_word_status(self):
        npc = NPCCard(name="Guard", occupation="guard")
        gs = _make_game_state_with_npc(npc)
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type="CHANGE_STATUS",
            target_id=npc.uuid,
            effect_data={"npc_id": npc.uuid, "status": "wounded left arm"},
        )
        applier.apply(effect)
        assert npc.physical_status == "wounded left arm"
