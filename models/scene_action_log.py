"""Per-scene action log for NPC short-term memory.

Each :class:`SceneActionEntry` records one chronological event in the
current scene — a player action, an NPC action/dialogue, or an ambient
witnessed event. The list is kept on
:attr:`models.game_state.GameState.scene_action_log`. At scene swap
:func:`cast.scene_swap.consolidate_outgoing_scene` hands it to
:func:`knowledge.scene_consolidation.consolidate_scene` for long-term
memory, then :mod:`cast.director_execution` clears the list (the
consolidate-then-clear ordering lives there, not in ``scene_swap``).

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

from pydantic import Field, model_validator

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

    @model_validator(mode="after")
    def _check_actor_identity(self) -> SceneActionEntry:
        """Enforce the ``actor_kind`` ↔ ``actor_uuid``/``actor_name`` matrix.

        PLAYER / NPC entries carry the acting entity's UUID; EVENT
        entries are anonymous (no UUID, empty name). Runs on
        construction and on JSONB rehydration
        (``SceneActionEntry(**raw)``), so a corrupted or stale row is
        rejected at the boundary instead of silently feeding the
        consolidator a malformed actor. ``actor_name`` is intentionally
        not required non-empty: it is derived from ``player.name`` /
        ``npc.name`` (both already defaulted upstream) and every
        consumer falls back gracefully on a blank label, so enforcing
        it here would only add a runtime failure mode without closing a
        real illegal state.
        """
        if self.actor_kind is ActorKind.EVENT:
            if self.actor_uuid is not None or self.actor_name:
                raise ValueError("EVENT entries must have actor_uuid=None and an empty actor_name")
            return self
        if self.actor_uuid is None:
            raise ValueError("{0} entries require a non-null actor_uuid".format(self.actor_kind.value))
        return self
