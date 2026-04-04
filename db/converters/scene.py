"""Scene ↔ DB row converters."""

from __future__ import annotations

from db.converters._columns import (
    COL_DESCRIPTION,
    COL_GAME_STATE_ID,
    COL_ID,
    COL_LOCATION_ID,
    COL_NPCS_PRESENT,
    COL_POINTS_OF_INTEREST,
)
from models.scene import Scene, SceneNPC


def scene_to_row(scene: Scene, game_state_id: str, is_current: bool = False, scene_number: int = 0) -> dict:
    return {
        COL_ID: scene.uuid,
        COL_GAME_STATE_ID: game_state_id,
        "is_current": is_current,
        "scene_number": scene_number,
        COL_LOCATION_ID: scene.location_id,
        COL_DESCRIPTION: scene.description,
        COL_NPCS_PRESENT: [snpc.to_dict() for snpc in scene.npcs_present],
        COL_POINTS_OF_INTEREST: scene.points_of_interest,
        "ambient_description": scene.ambient_description,
        "time_of_day": scene.time_of_day,
        "narrated_text": scene.narrated_text,
    }


def row_to_scene(row) -> Scene:
    # Backward-compatible: old rows store NPC UUIDs as plain strings.
    raw_npcs = row[COL_NPCS_PRESENT]
    npcs = [
        SceneNPC.from_dict(npc_entry)
        if isinstance(npc_entry, dict)
        else SceneNPC(role=npc_entry, uuid=npc_entry)  # legacy UUID string
        for npc_entry in raw_npcs
    ]
    scene = Scene(
        location_id=row[COL_LOCATION_ID],
        description=row[COL_DESCRIPTION],
        npcs_present=npcs,
        points_of_interest=row[COL_POINTS_OF_INTEREST],
        ambient_description=row["ambient_description"],
        time_of_day=row["time_of_day"],
    )
    scene.uuid = row[COL_ID]
    scene.narrated_text = row["narrated_text"]
    return scene
