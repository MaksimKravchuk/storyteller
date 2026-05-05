from __future__ import annotations

from uuid import UUID

from pydantic import ConfigDict, Field

from knowledge.graph import KnowledgeGraph
from models.base_model import StorytellerBase
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene
from models.setting import Setting
from models.visible_entity import VisibleEntity
from models.world_state import WorldState

INITIAL_GAME_CLOCK: float = float(0)


_DAWN_HOUR = 6
_NOON_HOUR = 12
_EVENING_HOUR = 18


def _time_of_day_label(hour_of_day: float) -> str:
    if hour_of_day < _DAWN_HOUR:
        return "night"
    if hour_of_day < _NOON_HOUR:
        return "morning"
    if hour_of_day < _EVENING_HOUR:
        return "afternoon"
    return "evening"


class PlayerState(StorytellerBase):
    """Mutable state for the player character.

    ``known_npcs`` carries the UUIDs of NPCs the player has been procedurally
    introduced to; the Narrator uses it to gate names vs. descriptors.
    ``player_event_log`` is a capped running log of notable turn outcomes
    (new NPC, completed event, object interaction) surfaced in the Character
    sidebar. ``learned_facts`` holds UUIDs of KnowledgeNodes the player has
    personally witnessed or been told.
    """

    name: str = "Player"
    location_id: UUID | None = None
    inventory: list[str] = []
    appearance: str = ""
    physical_status: str = "healthy"
    known_npcs: set[UUID] = Field(default_factory=set)
    player_event_log: list[str] = []
    learned_facts: set[UUID] = Field(default_factory=set)
    # Free-text era label the player chose at onboarding (e.g. "21st
    # century earth"). The :class:`AnachronismClassifier` reads it as
    # the deterministic anchor for "is this player action out of
    # period?". An empty string disables the classifier.
    origin_era: str = ""


class GameState(StorytellerBase):
    """Central mutable state for an active game session.

    Every agent receives a reference to the same ``GameState`` so they
    can read (and, where appropriate, update) the world.

    ``arbitrary_types_allowed`` is required because :class:`KnowledgeGraph`
    is a NetworkX-backed object with no pydantic schema.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    setting: Setting
    knowledge_graph: KnowledgeGraph
    player: PlayerState = Field(default_factory=PlayerState)
    current_scene: Scene | None = None
    locations: dict[UUID, Location] = {}
    npcs: dict[UUID, NPCCard] = {}
    turn_count: int = 0
    round_number: int = 0
    scene_number: int = 0
    game_clock: float = INITIAL_GAME_CLOCK
    game_time: str = "morning"
    conversation_log: list[dict] = []
    scene_conversation_log: list[dict] = []
    pending_clarification: list[dict] | None = None
    world_state: WorldState = Field(default_factory=WorldState)
    last_visible_entities: list[VisibleEntity] = []

    def advance_clock(self, hours: float) -> None:
        """Advance the game clock and update the time-of-day label."""
        _store_clock(self, self.game_clock + hours)


def _store_clock(state: GameState, new_clock: float) -> None:
    """Write the new clock and derived time-of-day label onto ``state``.

    Lives outside the class so the ``self.game_clock`` / ``self.game_time``
    assignments do not shadow the pydantic class-level defaults (WPS601).
    """
    state.game_clock = new_clock
    state.game_time = _time_of_day_label(new_clock % 24)
