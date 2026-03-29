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


# ── Setting ───────────────────────────────────────────────


def setting_to_row(setting: Setting, game_state_id: str) -> dict:
    return {
        "id": setting.uuid,
        "game_state_id": game_state_id,
        "name": setting.name,
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
    s = Setting(
        name=row["name"],
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
    s.uuid = row["id"]
    return s


# ── PlayerState ───────────────────────────────────────────


def player_to_row(player: PlayerState, game_state_id: str) -> dict:
    return {
        "id": player.uuid,
        "game_state_id": game_state_id,
        "name": player.name,
        "location_id": player.location_id,
        "inventory": player.inventory,
        "appearance": player.appearance,
        "interaction_history": player.interaction_history,
    }


def row_to_player(row) -> PlayerState:
    p = PlayerState(name=row["name"])
    p.uuid = row["id"]
    p.location_id = row["location_id"]
    p.inventory = row["inventory"]
    p.appearance = row["appearance"]
    p.interaction_history = row["interaction_history"]
    return p


# ── Location ─────────────────────────────────────────────


def location_to_row(loc: Location, game_state_id: str) -> dict:
    return {
        "id": loc.uuid,
        "game_state_id": game_state_id,
        "name": loc.name,
        "description": loc.description,
        "parent_location_id": loc.parent_location_id,
        "location_type": loc.location_type,
        "tags": loc.tags,
        "connected_locations": loc.connected_locations,
        "npcs_present": loc.npcs_present,
        "points_of_interest": loc.points_of_interest,
    }


def row_to_location(row) -> Location:
    loc = Location(
        name=row["name"],
        description=row["description"],
        parent_location_id=row["parent_location_id"],
        location_type=row["location_type"],
        tags=row["tags"],
        connected_locations=row["connected_locations"],
    )
    loc.uuid = row["id"]
    loc.npcs_present = row["npcs_present"]
    loc.points_of_interest = row["points_of_interest"]
    return loc


# ── NPCCard ──────────────────────────────────────────────


def npc_to_row(npc: NPCCard, game_state_id: str) -> dict:
    return {
        "id": npc.uuid,
        "game_state_id": game_state_id,
        "name": npc.name,
        "biography": npc.biography,
        "appearance": npc.appearance,
        "occupation": npc.occupation,
        "personality_traits": npc.personality_traits,
        "speech_style": npc.speech_style,
        "knowledge_scope": npc.knowledge_scope,
        "attributes": npc.attributes,
        "inventory": npc.inventory,
        "location_id": npc.location_id,
        "relationships": npc.relationships,
        "conversation_history": npc.conversation_history,
        "current_mood": npc.current_mood,
    }


def row_to_npc(row) -> NPCCard:
    npc = NPCCard(
        name=row["name"],
        biography=row["biography"],
        appearance=row["appearance"],
        occupation=row["occupation"],
        personality_traits=row["personality_traits"],
        speech_style=row["speech_style"],
        knowledge_scope=row["knowledge_scope"],
        attributes=row["attributes"],
        inventory=row["inventory"],
        location_id=row["location_id"],
        relationships=row["relationships"],
    )
    npc.uuid = row["id"]
    npc.conversation_history = row["conversation_history"]
    npc.current_mood = row["current_mood"]
    return npc


# ── Scene ────────────────────────────────────────────────


def scene_to_row(scene: Scene, game_state_id: str, is_current: bool = False) -> dict:
    return {
        "id": scene.uuid,
        "game_state_id": game_state_id,
        "is_current": is_current,
        "location_id": scene.location_id,
        "description": scene.description,
        "npcs_present": [snpc.to_dict() for snpc in scene.npcs_present],
        "points_of_interest": scene.points_of_interest,
        "ambient_description": scene.ambient_description,
        "time_of_day": scene.time_of_day,
        "narrated_text": scene.narrated_text,
    }


def row_to_scene(row) -> Scene:
    # Backward-compatible: old rows store NPC UUIDs as plain strings.
    raw_npcs = row["npcs_present"]
    npcs = [
        SceneNPC.from_dict(item) if isinstance(item, dict) else SceneNPC(role=item, uuid=item)  # legacy UUID string
        for item in raw_npcs
    ]
    s = Scene(
        location_id=row["location_id"],
        description=row["description"],
        npcs_present=npcs,
        points_of_interest=row["points_of_interest"],
        ambient_description=row["ambient_description"],
        time_of_day=row["time_of_day"],
    )
    s.uuid = row["id"]
    s.narrated_text = row["narrated_text"]
    return s


# ── KnowledgeNode ────────────────────────────────────────


def knowledge_node_to_row(node: KnowledgeNode, game_state_id: str) -> dict:
    return {
        "id": node.uuid,
        "game_state_id": game_state_id,
        "content": node.content,
        "scope": node.scope.value,
        "source": node.source.value,
        "required_education": node.required_education,
        "required_social_status": node.required_social_status,
        "tags": node.tags,
        "location_id": node.location_id,
        "timestamp": node.timestamp,
        "confidence": node.confidence,
    }


def row_to_knowledge_node(row) -> KnowledgeNode:
    node = KnowledgeNode(
        content=row["content"],
        scope=KnowledgeScope(row["scope"]),
        source=KnowledgeSource(row["source"]),
        required_education=row["required_education"],
        required_social_status=row["required_social_status"],
        tags=row["tags"],
        location_id=row["location_id"],
        timestamp=row["timestamp"],
        confidence=row["confidence"],
    )
    node.uuid = row["id"]
    return node


# ── GameEvent ────────────────────────────────────────────


def game_event_to_row(event: GameEvent, game_state_id: str) -> dict:
    return {
        "id": event.uuid,
        "game_state_id": game_state_id,
        "name": event.name,
        "scheduled_at": event.scheduled_at,
        "duration": event.duration,
        "completes_at": event.completes_at,
        "status": event.status.value,
        "owner_id": event.owner_id,
        "location_id": event.location_id,
        "scope": event.scope,
        "effects": [
            {"effect_type": e.effect_type, "target_id": e.target_id, "params": e.params} for e in event.effects
        ],
        "follow_up_events": event.follow_up_events,
        "on_complete_description": event.on_complete_description,
    }


def row_to_game_event(row) -> GameEvent:
    event = GameEvent(
        name=row["name"],
        scheduled_at=row["scheduled_at"],
        duration=row["duration"],
        owner_id=row["owner_id"],
        location_id=row["location_id"],
        scope=row["scope"],
        effects=[EventEffect(**e) for e in row["effects"]],
        follow_up_events=row["follow_up_events"],
        on_complete_description=row["on_complete_description"],
    )
    event.uuid = row["id"]
    event.status = EventStatus(row["status"])
    event.completes_at = row["completes_at"]
    return event
