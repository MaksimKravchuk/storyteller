"""Game event model — things that happen on a timeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from models.base_model import BaseModel


class EventStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class EventEffect:
    """A single state-change that is applied when an event completes.

    ``effect_type`` determines how ``effect_data`` is interpreted:
      - MOVE_NPC:          {"npc_id": str, "to_location_id": str}
      - ADD_ITEM:          {"npc_id": str, "item": str}
      - REMOVE_ITEM:       {"npc_id": str, "item": str}
      - ADD_KNOWLEDGE:     {"content": str, "scope": str, "tags": [...]}
      - CHANGE_ATTRIBUTE:  {"target_id": str, "attribute": str, "value": int}
      - SPAWN_NPC:         {"npc_request": str}   (triggers NPC generator)
      - REMOVE_NPC:        {"npc_id": str}
    """

    effect_type: str
    target_id: str
    effect_data: dict = field(default_factory=dict)


@dataclass(kw_only=True)
class GameEvent(BaseModel):
    """A scheduled event on the game timeline.

    Events are created by the Director / NPC Generator / Scene Builder
    and resolved by the EventManager when the game clock advances past
    their ``completes_at`` time.
    """

    name: str
    scheduled_at: float
    duration: float
    owner_id: str | None = None
    location_id: str | None = None
    scope: str = "local"
    effects: list[EventEffect] = field(default_factory=list)
    follow_up_events: list[dict] = field(default_factory=list)
    on_complete_description: str = ""
    completes_at: float = field(init=False)
    status: EventStatus = field(default=EventStatus.PENDING)

    def __post_init__(self) -> None:
        self.completes_at = self.scheduled_at + self.duration
