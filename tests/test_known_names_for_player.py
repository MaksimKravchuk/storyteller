"""Tests for :meth:`NPCCard.known_names_for_player`.

The new alias list drives the Narrator's natural-variation prompt AND
the entity-markup post-match. :meth:`label_for_player` is a thin
accessor over the first element, so both stay in lock-step.
"""

from __future__ import annotations

import allure
import pytest

from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.npc_card import NPCCard
from models.setting import Setting
from tests._uuid_helpers import make_uuid

_UUID = make_uuid("npc-1")


def _make_state() -> GameState:
    setting = Setting(name="Test", time_period="now", region="nowhere", summary="")
    return GameState(setting=setting, knowledge_graph=KnowledgeGraph())


def _make_npc(
    name: str = "Tony",
    occupation: str = "watchman",
    short_descriptor: str = "an armed man",
) -> NPCCard:
    npc = NPCCard(name=name, occupation=occupation, short_descriptor=short_descriptor)
    npc.uuid = _UUID
    return npc


@allure.epic("Narrator & UI")
@allure.feature("Player knowledge gating")
class TestKnownNamesForPlayer:
    @allure.story("Unknown NPC")
    @allure.title("Unknown NPC with short_descriptor yields only the descriptor")
    def test_unknown_with_descriptor(self):
        gs = _make_state()
        npc = _make_npc()
        assert npc.known_names_for_player(gs, role_fallback="guard") == ["an armed man"]

    @allure.story("Unknown NPC")
    @allure.title("Unknown NPC without a descriptor falls back to the SceneNPC role")
    def test_unknown_without_descriptor(self):
        gs = _make_state()
        npc = _make_npc(short_descriptor="")
        assert npc.known_names_for_player(gs, role_fallback="stranger") == ["stranger"]

    @allure.story("Introduced NPC")
    @allure.title("Introduced NPC with occupation exposes the combined form plus the bare name and 'the occupation'")
    def test_introduced_with_occupation(self):
        gs = _make_state()
        gs.player.known_npcs.add(_UUID)
        npc = _make_npc()
        names = npc.known_names_for_player(gs, role_fallback="guard")
        assert names == ["Tony (watchman)", "Tony", "the watchman"]

    @allure.story("Introduced NPC")
    @allure.title("Introduced NPC without an occupation returns only the name")
    def test_introduced_without_occupation(self):
        gs = _make_state()
        gs.player.known_npcs.add(_UUID)
        npc = _make_npc(occupation="")
        assert npc.known_names_for_player(gs, role_fallback="guard") == ["Tony"]

    @allure.story("Legacy accessor")
    @allure.title("label_for_player returns the primary name, matching the legacy 'Name (Occupation)' form")
    def test_label_for_player_matches_primary(self):
        gs = _make_state()
        gs.player.known_npcs.add(_UUID)
        npc = _make_npc()
        assert npc.label_for_player(gs, role_fallback="guard") == "Tony (watchman)"

    @allure.story("Legacy accessor")
    @allure.title("label_for_player preserves pre-introduction descriptor gating")
    @pytest.mark.parametrize(
        ("known", "descriptor", "expected"),
        [(False, "an armed man", "an armed man"), (False, "", "guard"), (True, "an armed man", "Tony (watchman)")],
    )
    def test_label_for_player_branches(self, known, descriptor, expected):
        gs = _make_state()
        npc = _make_npc(short_descriptor=descriptor or "")
        if known:
            gs.player.known_npcs.add(_UUID)
        assert npc.label_for_player(gs, role_fallback="guard") == expected

    @allure.story("Unknown NPC")
    @allure.title("A whitespace-only short_descriptor is treated as missing and falls back to the role")
    def test_whitespace_descriptor_falls_back(self):
        gs = _make_state()
        npc = _make_npc(short_descriptor="   ")
        assert npc.known_names_for_player(gs, role_fallback="stranger") == ["stranger"]
