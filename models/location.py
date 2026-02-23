from __future__ import annotations

from models.base_model import BaseModel


class Location(BaseModel):
    """A place in the game world.

    Locations form a hierarchy via ``parent_location_id``
    (building -> district -> city -> region -> country).
    """

    def __init__(
        self,
        *,
        name: str,
        description: str = "",
        parent_location_id: str | None = None,
        location_type: str = "generic",
        tags: list[str] | None = None,
        connected_locations: list[str] | None = None,
    ):
        super().__init__()
        self.name = name
        self.description = description
        self.parent_location_id = parent_location_id
        self.location_type = location_type  # "building", "district", "city", "region", "country"
        self.tags: list[str] = tags or []
        self.connected_locations: list[str] = connected_locations or []  # UUIDs
        self.npcs_present: list[str] = []  # NPC UUIDs currently at this location
        self.points_of_interest: list[str] = []

    def add_npc(self, npc_id: str) -> None:
        if npc_id not in self.npcs_present:
            self.npcs_present.append(npc_id)

    def remove_npc(self, npc_id: str) -> None:
        if npc_id in self.npcs_present:
            self.npcs_present.remove(npc_id)
