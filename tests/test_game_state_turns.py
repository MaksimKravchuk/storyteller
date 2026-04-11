"""Tests for turn/round tracking and PlayerState physical_status."""

from __future__ import annotations

import allure

from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.setting import Setting


def _make_game_state(**kwargs) -> GameState:
    kg = KnowledgeGraph()
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=kg,
        **kwargs,
    )


@allure.epic("Game Timeline")
@allure.feature("Turn & round tracking")
class TestPlayerStatePhysicalStatus:
    @allure.story("Player physical status")
    @allure.title("A freshly constructed PlayerState defaults to 'healthy' physical status")
    def test_default_is_healthy(self):
        ps = PlayerState()
        assert ps.physical_status == "healthy"

    @allure.story("Player physical status")
    @allure.title("PlayerState accepts a custom physical_status argument at construction time")
    def test_can_set_status(self):
        ps = PlayerState(physical_status="stunned")
        assert ps.physical_status == "stunned"

    @allure.story("Player physical status")
    @allure.title("GameState exposes the player's physical status through the player attribute")
    def test_game_state_player_has_status(self):
        gs = _make_game_state()
        assert gs.player.physical_status == "healthy"


@allure.epic("Game Timeline")
@allure.feature("Turn & round tracking")
class TestGameStateRoundNumber:
    @allure.story("Round number")
    @allure.title("A freshly constructed GameState starts with round_number equal to zero")
    def test_default_round_number_is_zero(self):
        gs = _make_game_state()
        assert gs.round_number == 0

    @allure.story("Round number")
    @allure.title("GameState accepts a non-zero round_number at construction time")
    def test_can_set_round_number(self):
        gs = _make_game_state(round_number=5)
        assert gs.round_number == 5
