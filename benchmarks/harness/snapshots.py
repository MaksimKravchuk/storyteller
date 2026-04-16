"""Before/after :class:`GameState` snapshots for deterministic scoring.

:class:`models.game_state.GameState` is a legacy dataclass (see
``models/base_model.py``), so Pydantic's ``model_copy(deep=True)`` is
unavailable. We fall back to :func:`copy.deepcopy`, which correctly
handles the networkx-backed :class:`KnowledgeGraph` and nested Pydantic
NPC cards without cross-turn aliasing.

Snapshots are captured *before* the first player action and *after*
each processed turn, producing a list of length ``len(script) + 1``.
Deterministic element checks can therefore index ``snapshots[i]`` for
state immediately after turn ``i`` and ``snapshots[0]`` for the pre-run
baseline.
"""

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


def conversation_history_len(snap: GameState, npc_uuid: str) -> int:
    """Return the length of an NPC's ``conversation_history`` list."""
    npc = snap.npcs.get(npc_uuid)
    return len(npc.conversation_history) if npc else 0
