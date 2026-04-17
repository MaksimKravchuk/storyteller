"""NPCCard ↔ DB row converters."""

from __future__ import annotations

from db.converters._columns import (
    COL_APPEARANCE,
    COL_GAME_STATE_ID,
    COL_ID,
    COL_INVENTORY,
    COL_LOCATION_ID,
    COL_NAME,
)
from models.npc_card import NPCCard


def npc_to_row(npc: NPCCard, game_state_id: str) -> dict:
    return {
        COL_ID: npc.uuid,
        COL_GAME_STATE_ID: game_state_id,
        COL_NAME: npc.name,
        "biography": npc.biography,
        COL_APPEARANCE: npc.appearance,
        "short_descriptor": npc.short_descriptor,
        "occupation": npc.occupation,
        "personality_traits": npc.personality_traits,
        "speech_style": npc.speech_style,
        "knowledge_scope": npc.knowledge_scope,
        "attributes": npc.attributes,
        COL_INVENTORY: npc.inventory,
        COL_LOCATION_ID: npc.location_id,
        "relationships": npc.relationships,
        "conversation_history": npc.conversation_history,
        "current_mood": npc.current_mood,
        "physical_status": npc.physical_status,
        "hostility_level": npc.hostility_level,
        "recent_hostile_actions": npc.recent_hostile_actions,
    }


def row_to_npc(row) -> NPCCard:
    return NPCCard(
        uuid=row[COL_ID],
        name=row[COL_NAME],
        biography=row["biography"],
        appearance=row[COL_APPEARANCE],
        short_descriptor=row.get("short_descriptor", ""),
        occupation=row["occupation"],
        personality_traits=row["personality_traits"],
        speech_style=row["speech_style"],
        knowledge_scope=row["knowledge_scope"],
        attributes=row["attributes"],
        inventory=row[COL_INVENTORY],
        location_id=row[COL_LOCATION_ID],
        relationships=row["relationships"],
        conversation_history=row["conversation_history"],
        current_mood=row["current_mood"],
        physical_status=row.get("physical_status", "healthy"),
        hostility_level=row.get("hostility_level", 0),
        recent_hostile_actions=row.get("recent_hostile_actions", []),
    )
