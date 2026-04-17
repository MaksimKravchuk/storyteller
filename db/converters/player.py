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
        _COL_KNOWN_NPCS: sorted(player.known_npcs),
        _COL_PLAYER_EVENT_LOG: player.player_event_log,
        _COL_LEARNED_FACTS: sorted(player.learned_facts),
    }


def row_to_player(row) -> PlayerState:
    player = PlayerState(name=row[COL_NAME])
    player.uuid = row[COL_ID]
    player.location_id = row[COL_LOCATION_ID]
    player.inventory = row[COL_INVENTORY]
    player.appearance = row[COL_APPEARANCE]
    player.interaction_history = row["interaction_history"]
    player.physical_status = row.get("physical_status", "healthy")
    player.known_npcs = set(row.get(_COL_KNOWN_NPCS) or [])
    player.player_event_log = list(row.get(_COL_PLAYER_EVENT_LOG) or [])
    player.learned_facts = set(row.get(_COL_LEARNED_FACTS) or [])
    return player
