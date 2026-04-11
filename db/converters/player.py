"""PlayerState ↔ DB row converters."""

from __future__ import annotations

from db.converters._columns import (
    COL_APPEARANCE,
    COL_GAME_STATE_ID,
    COL_ID,
    COL_INVENTORY,
    COL_LOCATION_ID,
    COL_NAME,
)
from models.game_state import PlayerState


def player_to_row(player: PlayerState, game_state_id: str) -> dict:
    return {
        COL_ID: player.uuid,
        COL_GAME_STATE_ID: game_state_id,
        COL_NAME: player.name,
        COL_LOCATION_ID: player.location_id,
        COL_INVENTORY: player.inventory,
        COL_APPEARANCE: player.appearance,
        "interaction_history": player.interaction_history,
        "physical_status": player.physical_status,
    }


def row_to_player(row) -> PlayerState:
    return PlayerState(
        uuid=row[COL_ID],
        name=row[COL_NAME],
        location_id=row[COL_LOCATION_ID],
        inventory=row[COL_INVENTORY],
        appearance=row[COL_APPEARANCE],
        interaction_history=row["interaction_history"],
        physical_status=row.get("physical_status", "healthy"),
    )
