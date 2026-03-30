"""Pure functions converting between domain objects and DB row dicts."""

from __future__ import annotations

from knowledge.node import (
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from models.game_state import PlayerState
from timeline.event import EventEffect, EventStatus, GameEvent

_COL_ID = "id"
_COL_GAME_STATE_ID = "game_state_id"
_COL_NAME = "name"
_COL_LOCATION_ID = "location_id"
_COL_INVENTORY = "inventory"
_COL_APPEARANCE = "appearance"
_COL_DESCRIPTION = "description"
_COL_TAGS = "tags"
_COL_NPCS_PRESENT = "npcs_present"
_COL_POINTS_OF_INTEREST = "points_of_interest"
_COL_SCOPE = "scope"


# ── Setting ───────────────────────────────────────────────


def setting_to_row(setting: Setting, game_state_id: str) -> dict:
    return {
        _COL_ID: setting.uuid,
        _COL_GAME_STATE_ID: game_state_id,
        _COL_NAME: setting.name,
        "time_period": setting.time_period,
        "region": setting.region,
        "summary": setting.summary,
        "key_persons": setting.key_persons,
        "key_events": setting.key_events,
        "locations_data": setting.locations,
        "traditions": setting.traditions,
        "technologies": setting.technologies,
        "social_structure": setting.social_structure,
        "raw_sources": setting.raw_sources,
    }


def row_to_setting(row) -> Setting:
    setting = Setting(
        name=row[_COL_NAME],
        time_period=row["time_period"],
        region=row["region"],
        summary=row["summary"],
        key_persons=row["key_persons"],
        key_events=row["key_events"],
        locations=row["locations_data"],
        traditions=row["traditions"],
        technologies=row["technologies"],
        social_structure=row["social_structure"],
        raw_sources=row["raw_sources"],
    )
    setting.uuid = row[_COL_ID]
    return setting


# ── PlayerState ───────────────────────────────────────────


def player_to_row(player: PlayerState, game_state_id: str) -> dict:
    return {
        _COL_ID: player.uuid,
        _COL_GAME_STATE_ID: game_state_id,
        _COL_NAME: player.name,
        _COL_LOCATION_ID: player.location_id,
        _COL_INVENTORY: player.inventory,
        _COL_APPEARANCE: player.appearance,
        "interaction_history": player.interaction_history,
    }


def row_to_player(row) -> PlayerState:
    player = PlayerState(name=row[_COL_NAME])
    player.uuid = row[_COL_ID]
    player.location_id = row[_COL_LOCATION_ID]
    player.inventory = row[_COL_INVENTORY]
    player.appearance = row[_COL_APPEARANCE]
    player.interaction_history = row["interaction_history"]
    return player


# ── Location ─────────────────────────────────────────────


def location_to_row(loc: Location, game_state_id: str) -> dict:
    return {
        _COL_ID: loc.uuid,
        _COL_GAME_STATE_ID: game_state_id,
        _COL_NAME: loc.name,
        _COL_DESCRIPTION: loc.description,
        "parent_location_id": loc.parent_location_id,
        "location_type": loc.location_type,
        _COL_TAGS: loc.tags,
        "connected_locations": loc.connected_locations,
        _COL_NPCS_PRESENT: loc.npcs_present,
        _COL_POINTS_OF_INTEREST: loc.points_of_interest,
    }


def row_to_location(row) -> Location:
    loc = Location(
        name=row[_COL_NAME],
        description=row[_COL_DESCRIPTION],
        parent_location_id=row["parent_location_id"],
        location_type=row["location_type"],
        tags=row[_COL_TAGS],
        connected_locations=row["connected_locations"],
    )
    loc.uuid = row[_COL_ID]
    loc.npcs_present = row[_COL_NPCS_PRESENT]
    loc.points_of_interest = row[_COL_POINTS_OF_INTEREST]
    return loc


# ── NPCCard ──────────────────────────────────────────────


def npc_to_row(npc: NPCCard, game_state_id: str) -> dict:
    return {
        _COL_ID: npc.uuid,
        _COL_GAME_STATE_ID: game_state_id,
        _COL_NAME: npc.name,
        "biography": npc.biography,
        _COL_APPEARANCE: npc.appearance,
        "occupation": npc.occupation,
        "personality_traits": npc.personality_traits,
        "speech_style": npc.speech_style,
        "knowledge_scope": npc.knowledge_scope,
        "attributes": npc.attributes,
        _COL_INVENTORY: npc.inventory,
        _COL_LOCATION_ID: npc.location_id,
        "relationships": npc.relationships,
        "conversation_history": npc.conversation_history,
        "current_mood": npc.current_mood,
    }


def row_to_npc(row) -> NPCCard:
    npc = NPCCard(
        name=row[_COL_NAME],
        biography=row["biography"],
        appearance=row[_COL_APPEARANCE],
        occupation=row["occupation"],
        personality_traits=row["personality_traits"],
        speech_style=row["speech_style"],
        knowledge_scope=row["knowledge_scope"],
        attributes=row["attributes"],
        inventory=row[_COL_INVENTORY],
        location_id=row[_COL_LOCATION_ID],
        relationships=row["relationships"],
    )
    npc.uuid = row[_COL_ID]
    npc.conversation_history = row["conversation_history"]
    npc.current_mood = row["current_mood"]
    return npc


# ── Scene ────────────────────────────────────────────────


def scene_to_row(scene: Scene, game_state_id: str, is_current: bool = False) -> dict:
    return {
        _COL_ID: scene.uuid,
        _COL_GAME_STATE_ID: game_state_id,
        "is_current": is_current,
        _COL_LOCATION_ID: scene.location_id,
        _COL_DESCRIPTION: scene.description,
        _COL_NPCS_PRESENT: [snpc.to_dict() for snpc in scene.npcs_present],
        _COL_POINTS_OF_INTEREST: scene.points_of_interest,
        "ambient_description": scene.ambient_description,
        "time_of_day": scene.time_of_day,
        "narrated_text": scene.narrated_text,
    }


def row_to_scene(row) -> Scene:
    # Backward-compatible: old rows store NPC UUIDs as plain strings.
    raw_npcs = row[_COL_NPCS_PRESENT]
    npcs = [
        SceneNPC.from_dict(npc_entry)
        if isinstance(npc_entry, dict)
        else SceneNPC(role=npc_entry, uuid=npc_entry)  # legacy UUID string
        for npc_entry in raw_npcs
    ]
    scene = Scene(
        location_id=row[_COL_LOCATION_ID],
        description=row[_COL_DESCRIPTION],
        npcs_present=npcs,
        points_of_interest=row[_COL_POINTS_OF_INTEREST],
        ambient_description=row["ambient_description"],
        time_of_day=row["time_of_day"],
    )
    scene.uuid = row[_COL_ID]
    scene.narrated_text = row["narrated_text"]
    return scene


# ── KnowledgeNode ────────────────────────────────────────


def knowledge_node_to_row(node: KnowledgeNode, game_state_id: str) -> dict:
    return {
        _COL_ID: node.uuid,
        _COL_GAME_STATE_ID: game_state_id,
        "content": node.content,
        _COL_SCOPE: node.scope.value,
        "source": node.source.value,
        "required_education": node.required_education,
        "required_social_status": node.required_social_status,
        _COL_TAGS: node.tags,
        _COL_LOCATION_ID: node.location_id,
        "timestamp": node.timestamp,
        "confidence": node.confidence,
    }


def row_to_knowledge_node(row) -> KnowledgeNode:
    node = KnowledgeNode(
        content=row["content"],
        scope=KnowledgeScope(row[_COL_SCOPE]),
        source=KnowledgeSource(row["source"]),
        required_education=row["required_education"],
        required_social_status=row["required_social_status"],
        tags=row[_COL_TAGS],
        location_id=row[_COL_LOCATION_ID],
        timestamp=row["timestamp"],
        confidence=row["confidence"],
    )
    node.uuid = row[_COL_ID]
    return node


# ── GameEvent ────────────────────────────────────────────


def game_event_to_row(event: GameEvent, game_state_id: str) -> dict:
    return {
        _COL_ID: event.uuid,
        _COL_GAME_STATE_ID: game_state_id,
        _COL_NAME: event.name,
        "scheduled_at": event.scheduled_at,
        "duration": event.duration,
        "completes_at": event.completes_at,
        "status": event.status.value,
        "owner_id": event.owner_id,
        _COL_LOCATION_ID: event.location_id,
        _COL_SCOPE: event.scope,
        "effects": [
            {"effect_type": eff.effect_type, "target_id": eff.target_id, "params": eff.params} for eff in event.effects
        ],
        "follow_up_events": event.follow_up_events,
        "on_complete_description": event.on_complete_description,
    }


def row_to_game_event(row) -> GameEvent:
    event = GameEvent(
        name=row[_COL_NAME],
        scheduled_at=row["scheduled_at"],
        duration=row["duration"],
        owner_id=row["owner_id"],
        location_id=row[_COL_LOCATION_ID],
        scope=row[_COL_SCOPE],
        effects=[EventEffect(**eff) for eff in row["effects"]],
        follow_up_events=row["follow_up_events"],
        on_complete_description=row["on_complete_description"],
    )
    event.uuid = row[_COL_ID]
    event.status = EventStatus(row["status"])
    event.completes_at = row["completes_at"]
    return event
