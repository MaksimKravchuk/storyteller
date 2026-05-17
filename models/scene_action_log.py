"""Per-scene action log for NPC short-term memory.

Each :class:`SceneActionEntry` records one chronological event in the
current scene — a player action, an NPC action/dialogue, or an ambient
witnessed event. The list is kept on
:attr:`models.game_state.GameState.scene_action_log` and is reset at
scene swap by the Director's plan executor, after being consolidated
into long-term memory by :func:`knowledge.scene_consolidation.consolidate_scene`
(driven from the scene-swap hook in :mod:`cast.scene_swap`).

NPCs see a chronological render of the log on every turn so they can
react to what happened earlier in the scene instead of just the last
player utterance. Entries flagged ``significant`` (NPC attacks,
aggressive player actions, intimidation wins, witnessed combat /
vandalism) become individual long-term nodes at scene end alongside
the per-NPC summary.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from models.base_model import StorytellerBase


class ActorKind(str, Enum):
    """Origin of a scene-log entry."""

    PLAYER = "player"
    NPC = "npc"
    EVENT = "event"


class SceneActionEntry(StorytellerBase):
    """One chronological event in the current scene.

    ``actor_uuid`` is None for ambient events (and resolves to the
    player's UUID for player entries when the caller passes it).
    ``actor_name`` carries a human-readable label for the NPC prompt
    render. ``description`` is free-text and is what the NPC sees and
    what the consolidator stores.

    ``significant=True`` flags entries that should become individual
    long-term memory nodes at scene end (in addition to the per-NPC
    summary). ``metadata["already_persisted"]=True`` is set by combat
    and witness hooks that already wrote a node via
    :meth:`MemoryManager.create_memory_from_event` so consolidation
    skips the duplicate.
    """

    actor_kind: ActorKind
    actor_uuid: UUID | None = None
    actor_name: str
    action_type: str
    description: str
    target_uuid: UUID | None = None
    target_name: str | None = None
    game_clock: float
    significant: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
