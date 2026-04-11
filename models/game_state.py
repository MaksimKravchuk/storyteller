from __future__ import annotations

from pydantic import ConfigDict, Field

from knowledge.graph import KnowledgeGraph
from models.base_model import StorytellerBase
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene
from models.setting import Setting

INITIAL_GAME_CLOCK: float = float(0)


_DAWN_HOUR = 6
_NOON_HOUR = 12
_EVENING_HOUR = 18


class PlayerState(StorytellerBase):
    """Mutable state for the player character."""

    name: str = "Player"
    location_id: str | None = None
    inventory: list[str] = []
    appearance: str = ""
    interaction_history: list[dict] = []
    physical_status: str = "healthy"


class GameState(StorytellerBase):
    """Central mutable state for an active game session.

    Every agent receives a reference to the same ``GameState`` so they
    can read (and, where appropriate, update) the world.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    setting: Setting
    knowledge_graph: KnowledgeGraph
    player: PlayerState = Field(default_factory=PlayerState)
    current_scene: Scene | None = None
    locations: dict[str, Location] = {}
    npcs: dict[str, NPCCard] = {}
    turn_count: int = 0
    round_number: int = 0
    scene_number: int = 0
    game_clock: float = INITIAL_GAME_CLOCK
    game_time: str = "morning"
    conversation_log: list[dict] = []
    scene_conversation_log: list[dict] = []
    pending_clarification: list[dict] | None = None

    def advance_clock(self, hours: float) -> None:
        """Advance the game clock and update time-of-day label."""
        self.game_clock += hours
        hour_of_day = self.game_clock % 24
        if hour_of_day < _DAWN_HOUR:
            self.game_time = "night"
        elif hour_of_day < _NOON_HOUR:
            self.game_time = "morning"
        elif hour_of_day < _EVENING_HOUR:
            self.game_time = "afternoon"
        else:
            self.game_time = "evening"
