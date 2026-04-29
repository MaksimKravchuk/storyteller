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

_COL_KNOWN_NPCS = "known_npcs"
_COL_PLAYER_EVENT_LOG = "player_event_log"
_COL_LEARNED_FACTS = "learned_facts"
_COL_PHYSICAL_STATUS = "physical_status"


def player_to_row(player: PlayerState, game_state_id: str) -> dict:
    return {
        COL_ID: player.uuid,
        COL_GAME_STATE_ID: game_state_id,
        COL_NAME: player.name,
        COL_LOCATION_ID: player.location_id,
        COL_INVENTORY: player.inventory,
        COL_APPEARANCE: player.appearance,
        _COL_PHYSICAL_STATUS: player.physical_status,
        _COL_KNOWN_NPCS: sorted(player.known_npcs),
        _COL_PLAYER_EVENT_LOG: player.player_event_log,
        _COL_LEARNED_FACTS: sorted(player.learned_facts),
    }


def row_to_player(row) -> PlayerState:
    return PlayerState(
        uuid=row[COL_ID],
        name=row[COL_NAME],
        location_id=row[COL_LOCATION_ID],
        inventory=row[COL_INVENTORY],
        appearance=row[COL_APPEARANCE],
        physical_status=row[_COL_PHYSICAL_STATUS],
        known_npcs=set(row[_COL_KNOWN_NPCS]),
        player_event_log=list(row[_COL_PLAYER_EVENT_LOG]),
        learned_facts=set(row[_COL_LEARNED_FACTS]),
    )
