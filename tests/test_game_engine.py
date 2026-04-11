"""Minimal smoke tests for GameEngine to guard public API regressions."""

from __future__ import annotations

import allure

from engine.game_engine import GameEngine

pytestmark = [allure.epic("Engine & LLM Infrastructure"), allure.feature("GameEngine public API")]


def _make_engine() -> GameEngine:
    return GameEngine()


@allure.story("State before start")
@allure.title("GameEngine exposes None for game_state before start_game has been called")
def test_game_state_is_none_before_start():
    """game_state property must exist and return None before start_game is called."""
    engine = _make_engine()
    assert engine.game_state is None
