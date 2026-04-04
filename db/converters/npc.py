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
    }


def row_to_npc(row) -> NPCCard:
    npc = NPCCard(
        name=row[COL_NAME],
        biography=row["biography"],
        appearance=row[COL_APPEARANCE],
        occupation=row["occupation"],
        personality_traits=row["personality_traits"],
        speech_style=row["speech_style"],
        knowledge_scope=row["knowledge_scope"],
        attributes=row["attributes"],
        inventory=row[COL_INVENTORY],
        location_id=row[COL_LOCATION_ID],
        relationships=row["relationships"],
    )
    npc.uuid = row[COL_ID]
    npc.conversation_history = row["conversation_history"]
    npc.current_mood = row["current_mood"]
    npc.physical_status = row.get("physical_status", "healthy")
    return npc
