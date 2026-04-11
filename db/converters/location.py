"""Location ↔ DB row converters."""

from __future__ import annotations

from db.converters._columns import (
    COL_DESCRIPTION,
    COL_GAME_STATE_ID,
    COL_ID,
    COL_NAME,
    COL_NPCS_PRESENT,
    COL_POINTS_OF_INTEREST,
    COL_TAGS,
)
from models.location import Location


def location_to_row(loc: Location, game_state_id: str) -> dict:
    return {
        COL_ID: loc.uuid,
        COL_GAME_STATE_ID: game_state_id,
        COL_NAME: loc.name,
        COL_DESCRIPTION: loc.description,
        "parent_location_id": loc.parent_location_id,
        "location_type": loc.location_type,
        COL_TAGS: loc.tags,
        "connected_locations": loc.connected_locations,
        COL_NPCS_PRESENT: loc.npcs_present,
        COL_POINTS_OF_INTEREST: loc.points_of_interest,
    }


def row_to_location(row) -> Location:
    return Location(
        uuid=row[COL_ID],
        name=row[COL_NAME],
        description=row[COL_DESCRIPTION],
        parent_location_id=row["parent_location_id"],
        location_type=row["location_type"],
        tags=row[COL_TAGS],
        connected_locations=row["connected_locations"],
        npcs_present=row[COL_NPCS_PRESENT],
        points_of_interest=row[COL_POINTS_OF_INTEREST],
    )
