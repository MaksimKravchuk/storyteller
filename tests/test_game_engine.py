"""Minimal smoke tests for GameEngine to guard public API regressions."""

from __future__ import annotations

import allure
import pytest

from defaults.models import AI_MODELS
from engine.game_engine import GameEngine, _apply_character_to_player
from models.game_state import PlayerState
from models.player_character_input import PlayerCharacterInput

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


@allure.story("Default models")
@allure.title("GameEngine() defaults the director, agent, and narrator roles to gpt-6-luna")
def test_default_role_models_are_gpt6_luna() -> None:
    engine = _make_engine()
    assert engine._director_model is AI_MODELS.gpt6_luna
    assert engine._agent_model is AI_MODELS.gpt6_luna
    assert engine._narrator_model is AI_MODELS.gpt6_luna


@allure.story("Character apply")
@allure.title("_apply_character_to_player copies appearance and inventory onto the player state")
def test_apply_character_copies_fields() -> None:
    player = PlayerState()
    character = PlayerCharacterInput(
        name="Alex",
        appearance="grey hoodie",
        inventory=["phone", "keys"],
        origin_era="modern day",
    )

    _apply_character_to_player(player, character)

    assert player.name == "Alex"
    assert player.appearance == "grey hoodie"
    assert player.inventory == ["phone", "keys"]
    assert player.origin_era == "modern day"


@allure.story("Character apply")
@allure.title("_apply_character_to_player preserves the default name when the input name is empty")
def test_apply_character_preserves_default_name_when_blank() -> None:
    player = PlayerState()
    character = PlayerCharacterInput(name="", appearance="x", inventory=[])

    _apply_character_to_player(player, character)

    assert player.name == "Player"
    assert player.appearance == "x"
    assert player.inventory == []


@allure.story("Character apply")
@allure.title("_apply_character_to_player copies the inventory as a fresh list (no aliasing)")
def test_apply_character_copies_inventory_list() -> None:
    player = PlayerState()
    items = ["phone"]
    character = PlayerCharacterInput(inventory=items)

    _apply_character_to_player(player, character)
    items.append("leaked")

    assert player.inventory == ["phone"]
