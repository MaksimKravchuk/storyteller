"""Schema for the World Chronicler LLM JSON response.

The World Chronicler is deliberately conservative: most scenes it
should return an empty ``ChroniclerResponse`` (defaults), and the
applier in :mod:`cast.director_execution` treats every field as
optional. All string identifiers (``thread_uuid``, ``location_id``)
reference existing UUIDs on :class:`models.game_state.GameState` —
the Chronicler never invents entities from scratch.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WorldThreadDraft(BaseModel):
    """A new world thread proposed by the Chronicler."""

    description: str
    category: Literal["personal", "political", "natural", "economic", "social", "cultural"]
    involved_locations: list[str] = Field(default_factory=list)
    involved_npcs: list[str] = Field(default_factory=list)


class WorldThreadUpdate(BaseModel):
    """An update to an existing world thread by UUID.

    ``status`` is the only field the Chronicler can currently change;
    other fields are immutable once the thread is created. A ``None``
    status means "keep the existing status", which bumps
    ``last_advanced_scene`` without closing the thread.
    """

    thread_uuid: str
    status: Literal["open", "resolved", "abandoned"] | None = None


class ScheduledEventDraft(BaseModel):
    """An offscreen ``GameEvent`` the Chronicler wants the timeline to resolve.

    ``hours_from_now`` is an offset (not an absolute game clock) so the
    Chronicler does not have to read ``game_state.game_clock`` itself.
    ``location_id`` may be ``None`` for world-level events; ``scope``
    defaults to ``"remote"`` because most Chronicler events happen
    out of sight of the player.
    """

    name: str
    hours_from_now: float
    location_id: str | None = None
    scope: Literal["local", "remote"] = "remote"
    on_complete_description: str = ""


class ChroniclerResponse(BaseModel):
    """Typed envelope for the Chronicler's per-scene updates.

    Every field defaults to empty / ``None`` so a conservative
    Chronicler can legitimately return ``{}``. The executor applies
    whichever fields are non-empty and leaves the rest alone.
    """

    new_threads: list[WorldThreadDraft] = Field(default_factory=list)
    thread_updates: list[WorldThreadUpdate] = Field(default_factory=list)
    scheduled_events: list[ScheduledEventDraft] = Field(default_factory=list)
    world_mood: str | None = None
