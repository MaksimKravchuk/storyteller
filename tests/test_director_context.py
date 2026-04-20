"""Tests for Director context formatting — NPC labels with physical status."""

from __future__ import annotations

import allure

from cast.director_context import ContextFormatter, format_npcs_present
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from models.visible_entity import VisibleEntity

_GUARD_NAME = "Guard"
_GUARD = "guard"
_LOC = "loc1"


def _make_game_state_with_npcs(npc_list: list[NPCCard]) -> GameState:
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    for npc in npc_list:
        gs.npcs[npc.uuid] = npc
    return gs


@allure.epic("NPC Interaction")
@allure.feature("Director context formatting")
@allure.story("NPC label formatting")
class TestFormatNpcsPresent:
    @allure.title("A healthy NPC in the scene renders as just the NPC's name with no status suffix")
    def test_healthy_npc_shows_name_only(self):
        npc = NPCCard(name=_GUARD_NAME, occupation=_GUARD, physical_status="healthy")
        gs = _make_game_state_with_npcs([npc])
        scene = Scene(
            location_id=_LOC,
            npcs_present=[SceneNPC(role=_GUARD, uuid=npc.uuid)],
        )
        formatted = format_npcs_present(scene, gs)
        assert formatted == _GUARD_NAME

    @allure.title("A wounded NPC renders as 'Name (wounded left arm)' in the scene label string")
    def test_wounded_npc_shows_status(self):
        npc = NPCCard(name=_GUARD_NAME, occupation=_GUARD, physical_status="wounded left arm")
        gs = _make_game_state_with_npcs([npc])
        scene = Scene(
            location_id=_LOC,
            npcs_present=[SceneNPC(role=_GUARD, uuid=npc.uuid)],
        )
        formatted = format_npcs_present(scene, gs)
        assert formatted == "{0} (wounded left arm)".format(_GUARD_NAME)

    @allure.title("A scene with mixed healthy and wounded NPCs only appends status to the wounded ones")
    def test_mixed_healthy_and_wounded(self):
        guard = NPCCard(name=_GUARD_NAME, occupation=_GUARD, physical_status="barely standing")
        merchant = NPCCard(name="Merchant", occupation="merchant", physical_status="healthy")
        gs = _make_game_state_with_npcs([guard, merchant])
        scene = Scene(
            location_id=_LOC,
            npcs_present=[
                SceneNPC(role=_GUARD, uuid=guard.uuid),
                SceneNPC(role="merchant", uuid=merchant.uuid),
            ],
        )
        formatted = format_npcs_present(scene, gs)
        assert "{0} (barely standing)".format(_GUARD_NAME) in formatted
        assert "Merchant" in formatted
        assert "(healthy)" not in formatted

    @allure.title("When the scene is None, the NPC-present formatter returns the literal string 'None'")
    def test_no_scene_returns_none(self):
        gs = _make_game_state_with_npcs([])
        assert format_npcs_present(None, gs) == "None"


@allure.epic("NPC Interaction")
@allure.feature("Director context formatting")
@allure.story("Turn log snapshot")
class TestAppendTurnLogsVisibleEntities:
    @allure.title("append_turn_logs snapshots last_visible_entities into the new conversation_log entry")
    def test_visible_entities_serialized_into_log(self) -> None:
        gs = _make_game_state_with_npcs([])
        gs.last_visible_entities = [
            VisibleEntity(kind="npc", id="npc-1", names=["an armed man"]),
            VisibleEntity(kind="poi", id="poi-1", names=["notice board", "board"]),
        ]
        ContextFormatter(gs).append_turn_logs("look", "You see the gate.", "EXPLORE")
        entry = gs.conversation_log[-1]
        assert entry["visible_entities"] == [
            {"kind": "npc", "id": "npc-1", "names": ["an armed man"]},
            {"kind": "poi", "id": "poi-1", "names": ["notice board", "board"]},
        ]

    @allure.title("append_turn_logs writes an empty visible_entities list when the narrator produced none")
    def test_empty_visible_entities_still_serialized(self) -> None:
        gs = _make_game_state_with_npcs([])
        ContextFormatter(gs).append_turn_logs("look", "Silence.", "EXPLORE")
        assert gs.conversation_log[-1]["visible_entities"] == []
