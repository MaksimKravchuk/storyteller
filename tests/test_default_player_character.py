"""Tests for the canned ``TEMPLATE_CHARACTER`` constant.

The template doubles as the deterministic default for tests and the
backing payload for the web UI's "Use template" button. These tests
guard against accidental blanking and ensure the constant always
satisfies :class:`PlayerCharacterInput` validation.
"""

from __future__ import annotations

import allure

from defaults.player_character import TEMPLATE_CHARACTER
from models.player_character_input import PlayerCharacterInput

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Character creation"),
    allure.story("Template character"),
]


@allure.title("TEMPLATE_CHARACTER is a valid PlayerCharacterInput instance")
def test_template_is_player_character_input() -> None:
    assert isinstance(TEMPLATE_CHARACTER, PlayerCharacterInput)


@allure.title("TEMPLATE_CHARACTER carries a non-empty appearance and inventory")
def test_template_has_visual_attributes_and_inventory() -> None:
    assert TEMPLATE_CHARACTER.appearance.strip()
    assert TEMPLATE_CHARACTER.inventory
    # No empty items leaked in.
    assert all(item.strip() for item in TEMPLATE_CHARACTER.inventory)
