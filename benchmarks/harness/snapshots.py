"""Before/after :class:`GameState` snapshots for deterministic scoring."""

from __future__ import annotations

import copy

from models.game_state import GameState


def snapshot(game_state: GameState) -> GameState:
    """Return a deep copy of ``game_state`` safe to compare with the original."""
    return copy.deepcopy(game_state)


def mood_of(snap: GameState, npc_uuid: str) -> str | None:
    """Return an NPC's ``current_mood`` in a snapshot, or ``None`` when absent."""
    npc = snap.npcs.get(npc_uuid)
    return npc.current_mood if npc else None


def physical_status_of(snap: GameState, npc_uuid: str) -> str | None:
    """Return an NPC's ``physical_status`` in a snapshot, or ``None`` when absent."""
    npc = snap.npcs.get(npc_uuid)
    return npc.physical_status if npc else None


def hostility_level_of(snap: GameState, npc_uuid: str) -> int:
    """Return an NPC's ``hostility_level`` in a snapshot, or ``0`` when absent."""
    npc = snap.npcs.get(npc_uuid)
    return npc.hostility_level if npc else 0


def conversation_history_len(snap: GameState, npc_uuid: str) -> int:
    """Return the length of an NPC's ``conversation_history`` list."""
    npc = snap.npcs.get(npc_uuid)
    return len(npc.conversation_history) if npc else 0
