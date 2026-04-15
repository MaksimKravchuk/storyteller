from __future__ import annotations

from pydantic import Field

from models.base_model import StorytellerBase


class Location(StorytellerBase):
    """A place in the game world.

    Locations form a hierarchy via ``parent_location_id``
    (building -> district -> city -> region -> country).
    """

    name: str
    description: str = ""
    parent_location_id: str | None = None
    location_type: str = "generic"  # "building", "district", "city", "region", "country"
    tags: list[str] = []
    connected_locations: list[str] = []  # UUIDs
    npcs_present: list[str] = []  # NPC UUIDs currently at this location
    points_of_interest: list[str] = []
    object_states: dict[str, str] = Field(default_factory=dict)

    def add_npc(self, npc_id: str) -> None:
        if npc_id not in self.npcs_present:
            self.npcs_present.append(npc_id)

    def remove_npc(self, npc_id: str) -> None:
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
