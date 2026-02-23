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

    ``effect_type`` determines how ``params`` is interpreted:
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
    params: dict = field(default_factory=dict)


class GameEvent(BaseModel):
    """A scheduled event on the game timeline.

    Events are created by the Director / NPC Generator / Scene Builder
    and resolved by the EventManager when the game clock advances past
    their ``completes_at`` time.
    """

    def __init__(
        self,
        *,
        name: str,
        scheduled_at: float,
        duration: float,
        owner_id: str | None = None,
        location_id: str | None = None,
        scope: str = "local",
        effects: list[EventEffect] | None = None,
        follow_up_events: list[dict] | None = None,
        on_complete_description: str = "",
    ):
        super().__init__()
        self.name = name
        self.scheduled_at = scheduled_at
        self.duration = duration
        self.completes_at: float = scheduled_at + duration
        self.status: EventStatus = EventStatus.PENDING
        self.owner_id = owner_id          # NPC UUID or None for world events
        self.location_id = location_id    # Where the event takes place
        self.scope = scope                # "local"/"city"/"region"/"country"/"world"
        self.effects: list[EventEffect] = effects or []
        self.follow_up_events: list[dict] = follow_up_events or []
        self.on_complete_description = on_complete_description
