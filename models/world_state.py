"""WorldState and supporting models for the living-world sandbox.

``WorldState`` tracks ongoing situations (``WorldThread``), a persistent
``world_mood`` hint for the Narrator, and the last scene the World
Chronicler advanced. Unlike the earlier plot-driven sketch it replaces,
none of these fields impose dramatic-beat structure on the game — the
world evolves whether or not there is a plot.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from models.base_model import StorytellerBase

ThreadCategory = Literal["personal", "political", "natural", "economic", "social", "cultural"]
ThreadStatus = Literal["open", "resolved", "abandoned"]


class WorldThread(StorytellerBase):
    """An ongoing situation in the world, player-aware or not.

    ``category`` classifies what kind of thread it is so the Chronicler
    can keep the overall mix varied across scenes. ``involved_locations``
    and ``involved_npcs`` are UUIDs referencing ``GameState.locations``
    and ``GameState.npcs`` respectively. ``last_advanced_scene`` records
    the scene number the thread was last touched, which lets the
    Chronicler prefer advancing stale threads over creating new ones.
    """

    description: str
    category: ThreadCategory
    introduced_scene: int
    involved_locations: list[str] = []
    involved_npcs: list[str] = []
    status: ThreadStatus = "open"
    last_advanced_scene: int = 0


class WorldState(BaseModel):
    """Living-world state. NOT plot structure.

    ``threads`` are ongoing situations the Chronicler tracks and advances.
    ``world_mood`` is a short atmospheric hint the Narrator reads each
    turn. ``last_chronicled_scene`` records the last scene number the
    Chronicler ran so the agent can decide whether it owes a new update.

    ``extra="ignore"`` lets legacy JSONB rows that still carry a
    ``uuid`` key deserialize cleanly after the field was dropped.
    """

    model_config = ConfigDict(extra="ignore")

    threads: list[WorldThread] = []
    world_mood: str | None = None
    last_chronicled_scene: int = 0
