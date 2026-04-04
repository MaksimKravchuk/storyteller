"""Tests for turn/round tracking and PlayerState physical_status."""

from __future__ import annotations

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


class TestPlayerStatePhysicalStatus:
    def test_default_is_healthy(self):
        ps = PlayerState()
        assert ps.physical_status == "healthy"

    def test_can_set_status(self):
        ps = PlayerState(physical_status="stunned")
        assert ps.physical_status == "stunned"

    def test_game_state_player_has_status(self):
        gs = _make_game_state()
        assert gs.player.physical_status == "healthy"


class TestGameStateRoundNumber:
    def test_default_round_number_is_zero(self):
        gs = _make_game_state()
        assert gs.round_number == 0

    def test_can_set_round_number(self):
        gs = _make_game_state(round_number=5)
        assert gs.round_number == 5
