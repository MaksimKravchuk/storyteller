from __future__ import annotations

from typing import TYPE_CHECKING

from models.base_model import BaseModel

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.location import Location
    from models.npc_card import NPCCard
    from models.scene import Scene
    from models.setting import Setting


class PlayerState(BaseModel):
    """Mutable state for the player character."""

    def __init__(self, *, name: str = "Player"):
        super().__init__()
        self.name = name
        self.location_id: str | None = None
        self.inventory: list[str] = []
        self.appearance: str = ""
        self.interaction_history: list[dict] = []  # {action, response, timestamp}


class GameState(BaseModel):
    """Central mutable state for an active game session.

    Every agent receives a reference to the same ``GameState`` so they
    can read (and, where appropriate, update) the world.
    """

    def __init__(
        self,
        *,
        setting: Setting,
        knowledge_graph: KnowledgeGraph,
    ):
        super().__init__()
        self.setting: Setting = setting
        self.knowledge_graph: KnowledgeGraph = knowledge_graph
        self.player: PlayerState = PlayerState()
        self.current_scene: Scene | None = None
        self.locations: dict[str, Location] = {}  # UUID -> Location
        self.npcs: dict[str, NPCCard] = {}  # UUID -> NPCCard
        self.turn_count: int = 0
        self.game_clock: float = 0.0  # Game time in hours
        self.game_time: str = "morning"  # Human-readable time of day
        self.conversation_log: list[dict] = []  # Full session log
        # Pending clarification exchange for the Director (persisted so it
        # survives engine recreation between Telegram messages).
        self.pending_clarification: list[dict] | None = None

    def advance_clock(self, hours: float) -> None:
        """Advance the game clock and update time-of-day label."""
        self.game_clock += hours
        hour_of_day = self.game_clock % 24
        if hour_of_day < 6:
            self.game_time = "night"
        elif hour_of_day < 12:
            self.game_time = "morning"
        elif hour_of_day < 18:
            self.game_time = "afternoon"
        else:
            self.game_time = "evening"
