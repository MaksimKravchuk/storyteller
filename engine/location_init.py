"""Promote ``Setting.locations`` dicts into ``game_state.locations`` and anchor the player."""

from __future__ import annotations

from models.game_state import GameState
from models.location import Location


def materialise_setting_locations(game_state: GameState) -> None:
    """Promote ``setting.locations`` dicts into ``Location`` instances; anchor the player on the first.

    No-op when ``game_state.locations`` already has entries — restored
    sessions arrive with locations already loaded and the player's
    anchor preserved.
    """
    if game_state.locations:
        return
    for entry in game_state.setting.locations:
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        loc = Location(
            name=name,
            description=entry.get("description", ""),
            location_type=entry.get("type") or "generic",
        )
        game_state.locations[loc.uuid] = loc
        if game_state.player.location_id is None:
            game_state.player.location_id = loc.uuid
