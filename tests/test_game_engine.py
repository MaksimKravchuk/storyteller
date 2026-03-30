"""Minimal smoke tests for GameEngine to guard public API regressions."""

from __future__ import annotations

from engine.game_engine import GameEngine


def _make_engine() -> GameEngine:
    return GameEngine()


def test_game_state_is_none_before_start():
    """game_state property must exist and return None before start_game is called."""
    engine = _make_engine()
    assert engine.game_state is None
