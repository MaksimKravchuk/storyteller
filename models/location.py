from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from models.base_model import StorytellerBase
from models.scene import PointOfInterest, _coerce_points_of_interest


class Location(StorytellerBase):
    """A place in the game world.

    Locations form a hierarchy via ``parent_location_id``
    (building -> district -> city -> region -> country).
    """

    model_config = ConfigDict(validate_assignment=True)

    name: str
    description: str = ""
    parent_location_id: UUID | None = None
    location_type: str = "generic"  # "building", "district", "city", "region", "country"
    tags: list[str] = []
    connected_locations: list[UUID] = []
    npcs_present: list[UUID] = []  # NPC UUIDs currently at this location
    points_of_interest: list[PointOfInterest] = []
    object_states: dict[str, str] = Field(default_factory=dict)

    def add_npc(self, npc_id: UUID) -> None:
        if npc_id not in self.npcs_present:
            self.npcs_present.append(npc_id)

    def remove_npc(self, npc_id: UUID) -> None:
        if npc_id in self.npcs_present:
            self.npcs_present.remove(npc_id)

    def record_object_state(self, object_key: str, state_description: str) -> bool:
        """Write a normalized object_state entry and return whether it took effect.

        Consolidates the empty-string guard and key normalization that
        every producer would otherwise re-implement. Keys are lowercased
        and underscores collapse to spaces so that ``"wooden_shutter"``,
        ``"Wooden Shutter"``, and ``"wooden shutter"`` all land in the
        same slot — the scene-prose substring match downstream depends
        on this alignment. Returns ``True`` when a value was written so
        callers can fail loudly on bad input if they want to.
        """
        normalized_key = object_key.strip().lower().replace("_", " ")
        if not normalized_key or not state_description:
            return False
        self.object_states[normalized_key] = state_description
        return True

    @field_validator("points_of_interest", mode="before")
    @classmethod
    def _coerce_pois(cls, raw: Any) -> list[PointOfInterest]:
        return _coerce_points_of_interest(raw)
