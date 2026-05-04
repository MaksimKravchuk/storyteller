"""GameState builders shared by :mod:`test_memory_slots`.

Each builder returns a minimal state wired up for one consumer-seam
scenario (combat, co-witness broadcast, effect-driven memory).
"""

from __future__ import annotations

from uuid import UUID

from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from tests._uuid_helpers import make_uuid
from timeline.effect_memory import EffectPreState

PLAYER_NAME = "Aelia"
LOC = make_uuid("loc-forum")
BRUTUS = make_uuid("npc-brutus")
MARCUS = make_uuid("npc-marcus")
LIVIA = make_uuid("npc-livia")


def _bare_state() -> GameState:
    return GameState(
        setting=Setting(name="Test", time_period="now", region="lab", summary=""),
        knowledge_graph=KnowledgeGraph(),
        player=PlayerState(name=PLAYER_NAME, location_id=LOC),
    )


def make_combat_state() -> tuple[GameState, NPCCard, NPCCard]:
    """Two co-located NPCs (Brutus + Marcus) at LOC, registered in a Scene."""
    actor = NPCCard(name="Brutus", occupation="legionary")
    actor.uuid = BRUTUS
    actor.location_id = LOC
    target = NPCCard(name="Marcus", occupation="merchant")
    target.uuid = MARCUS
    target.location_id = LOC
    location = Location(name="Forum", description="", location_type="square")
    location.uuid = LOC
    location.npcs_present = [BRUTUS, MARCUS]
    state = _bare_state()
    state.locations[LOC] = location
    state.npcs[BRUTUS] = actor
    state.npcs[MARCUS] = target
    state.current_scene = Scene(
        location_id=LOC,
        description="",
        npcs_present=[
            SceneNPC(role=actor.occupation, uuid=BRUTUS),
            SceneNPC(role=target.occupation, uuid=MARCUS),
        ],
    )
    return state, actor, target


def make_cowitness_state() -> GameState:
    """Marcus (target) and Livia (co-witness) initialised in a single Scene."""
    state = _bare_state()
    location = Location(name="Forum", description="", location_type="square")
    location.uuid = LOC
    state.locations[LOC] = location
    marcus = NPCCard(name="Marcus", occupation="merchant")
    marcus.uuid = MARCUS
    livia = NPCCard(name="Livia", occupation="vendor")
    livia.uuid = LIVIA
    state.npcs[MARCUS] = marcus
    state.npcs[LIVIA] = livia
    state.current_scene = Scene(
        location_id=LOC,
        description="",
        npcs_present=[
            SceneNPC(role=marcus.occupation, uuid=MARCUS),
            SceneNPC(role=livia.occupation, uuid=LIVIA),
        ],
    )
    return state


def state_with_target_at(loc_id: UUID, npc_id: UUID, npc_name: str) -> tuple[GameState, EffectPreState]:
    """Two NPCs at ``loc_id`` (target + Livia bystander) and a pre-state for ``npc_id``."""
    state = GameState(
        setting=Setting(name="Test", time_period="now", region="lab", summary=""),
        knowledge_graph=KnowledgeGraph(),
        player=PlayerState(name=PLAYER_NAME),
    )
    location = Location(name="Forum", description="", location_type="square")
    location.uuid = loc_id
    location.npcs_present = [npc_id, LIVIA]
    state.locations[loc_id] = location
    pre = EffectPreState(npc_id=npc_id, npc_name=npc_name, location_id=loc_id)
    return state, pre


def make_event_state() -> GameState:
    """Bare state with no scene — just enough for EventProcessor to build memories."""
    return GameState(
        setting=Setting(name="Test", time_period="now", region="lab", summary=""),
        knowledge_graph=KnowledgeGraph(),
        player=PlayerState(name=PLAYER_NAME),
    )
