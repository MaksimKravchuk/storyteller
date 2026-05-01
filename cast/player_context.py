"""Helpers for projecting :class:`models.game_state.PlayerState` into prompt context."""

from __future__ import annotations

from typing import Any

_DEFAULT_APPEARANCE = "unremarkable"
_DEFAULT_INVENTORY = "nothing of note"


def format_player_appearance(player: Any) -> str:
    """Return appearance or a fallback so the player_character PromptSection always renders."""
    return player.appearance or _DEFAULT_APPEARANCE


def format_player_inventory(player: Any) -> str:
    """Return inventory comma-joined or a fallback so the PromptSection always renders."""
    if not player.inventory:
        return _DEFAULT_INVENTORY
    return ", ".join(player.inventory)
