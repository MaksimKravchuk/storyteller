"""WorldState and supporting dataclasses for the living-world sandbox.

``WorldState`` tracks ongoing situations (``WorldThread``), a persistent
``world_mood`` hint for the Narrator, and the last scene the World
Chronicler advanced. Unlike the earlier plot-driven sketch it replaces,
none of these fields impose dramatic-beat structure on the game — the
world evolves whether or not there is a plot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from models.base_model import BaseModel

ThreadCategory = Literal["personal", "political", "natural", "economic", "social", "cultural"]
ThreadStatus = Literal["open", "resolved", "abandoned"]


@dataclass(kw_only=True)
class WorldThread(BaseModel):
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
    involved_locations: list[str] = field(default_factory=list)
    involved_npcs: list[str] = field(default_factory=list)
    status: ThreadStatus = "open"
    last_advanced_scene: int = 0


@dataclass(kw_only=True)
class WorldState(BaseModel):
    """Living-world state. NOT plot structure.

    ``threads`` are ongoing situations the Chronicler tracks and advances.
    ``world_mood`` is a short atmospheric hint the Narrator reads each
    turn. ``last_chronicled_scene`` records the last scene number the
    Chronicler ran so the agent can decide whether it owes a new update.
    """

    threads: list[WorldThread] = field(default_factory=list)
    world_mood: str | None = None
    last_chronicled_scene: int = 0
