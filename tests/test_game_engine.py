"""Minimal smoke tests for GameEngine to guard public API regressions."""

from __future__ import annotations

import allure
import pytest

from engine.game_engine import GameEngine

pytestmark = [allure.epic("Engine & LLM Infrastructure"), allure.feature("GameEngine public API")]


def _make_engine() -> GameEngine:
    return GameEngine()


@allure.story("State before start")
@allure.title("GameEngine.assert_running raises RuntimeError before start_game has been called")
def test_assert_running_raises_before_start():
    """assert_running must raise before start_game has wired all components."""
    engine = _make_engine()
    with pytest.raises(RuntimeError, match="Game not started"):
        engine.assert_running()
