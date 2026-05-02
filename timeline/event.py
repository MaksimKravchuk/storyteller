"""Game event model — things that happen on a timeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from typing import Any

from pydantic import model_validator

from models.base_model import StorytellerBase


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
      - CHANGE_STATUS:     {"npc_id": str, "status": str}
      - APPLY_OBJECT_DAMAGE:
          {"location_id": str, "object_key": str, "state_description": str}
      - SPAWN_NPC:         {"npc_request": str}   (triggers NPC generator)
      - REMOVE_NPC:        {"npc_id": str}
    """

    effect_type: str
    target_id: str
    effect_data: dict = field(default_factory=dict)


class GameEvent(StorytellerBase):
    """A scheduled event on the game timeline.

    Events are created by the Director / NPC Generator / Scene Builder
    and resolved by the EventManager when the game clock advances past
    their ``completes_at`` time.
    """

    name: str
    scheduled_at: float
    duration: float
    owner_id: UUID | None = None
    location_id: UUID | None = None
    scope: str = "local"
    effects: list[EventEffect] = []
    on_complete_description: str = ""
    completes_at: float = float(0)
    status: EventStatus = EventStatus.PENDING

    @model_validator(mode="before")
    @classmethod
    def _derive_completes_at(cls, raw_values: Any) -> Any:
        """Populate ``completes_at`` from ``scheduled_at + duration`` when unset.

        Callers (Director, NPC generator, ...) don't pass ``completes_at``;
        converters rehydrating from a DB row pass it explicitly, so only
        compute it when the key is missing.
        """
        if isinstance(raw_values, dict) and "completes_at" not in raw_values:
            scheduled_at = raw_values.get("scheduled_at")
            duration = raw_values.get("duration")
            if scheduled_at is not None and duration is not None:
                raw_values["completes_at"] = scheduled_at + duration
        return raw_values
