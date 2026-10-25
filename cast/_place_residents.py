"""Who lives or works at a place, and who is there right now.

Residency is ``Location.npcs_present`` — NPCs are added on registration
and removed when they die or leave — and presence right now is the
occupation schedule from :mod:`cast.npc_ticker`.
"""

from __future__ import annotations

from uuid import UUID

from cast.npc_ticker import get_schedule_for
from models.game_state import GameState
from models.npc_card import NPCCard

_STATUS_DEAD = "dead"
_MAX_RESIDENTS_SEATED = 5


def present_residents(game_state: GameState, location_id: UUID | None) -> list[NPCCard]:
    """Return the NPCs who belong at *location_id* and are there right now.

    People the player has met come first; the list is capped so a place
    that accumulated many background NPCs does not flood every scene.
    """
    time_of_day = game_state.game_time
    residents = [npc for npc in _residents(game_state, location_id) if _is_there_now(npc, time_of_day)]
    residents.sort(key=lambda npc: not _player_has_met(game_state, npc))
    return residents[:_MAX_RESIDENTS_SEATED]


def resident_named(game_state: GameState, location_id: UUID | None, name: str) -> NPCCard | None:
    """Return the living resident of *location_id* called *name*, schedule regardless."""
    wanted = name.strip().lower()
    for npc in _residents(game_state, location_id):
        if npc.name.lower() == wanted and _is_alive(npc):
            return npc
    return None


def _residents(game_state: GameState, location_id: UUID | None) -> list[NPCCard]:
    location = game_state.locations.get(location_id) if location_id else None
    if location is None:
        return []
    residents: list[NPCCard] = []
    for npc_id in location.npcs_present:
        npc = game_state.npcs.get(npc_id)
        if npc is not None:
            residents.append(npc)
    return residents


def _is_there_now(npc: NPCCard, time_of_day: str) -> bool:
    if not _is_alive(npc):
        return False
    slot = get_schedule_for(npc.occupation).get(time_of_day)
    return slot is None or slot.present


def _is_alive(npc: NPCCard) -> bool:
    return (npc.physical_status or "").lower() != _STATUS_DEAD


def _player_has_met(game_state: GameState, npc: NPCCard) -> bool:
    return npc.uuid in game_state.player.known_npcs or bool(npc.conversation_history)
