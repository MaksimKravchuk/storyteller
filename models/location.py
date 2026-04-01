from __future__ import annotations

from dataclasses import dataclass, field

from models.base_model import BaseModel


@dataclass(kw_only=True)
class Location(BaseModel):
    """A place in the game world.

    Locations form a hierarchy via ``parent_location_id``
    (building -> district -> city -> region -> country).
    """

    name: str
    description: str = ""
    parent_location_id: str | None = None
    location_type: str = "generic"  # "building", "district", "city", "region", "country"
    tags: list[str] = field(default_factory=list)
    connected_locations: list[str] = field(default_factory=list)  # UUIDs
    npcs_present: list[str] = field(default_factory=list)  # NPC UUIDs currently at this location
    points_of_interest: list[str] = field(default_factory=list)

    def add_npc(self, npc_id: str) -> None:
        if npc_id not in self.npcs_present:
            self.npcs_present.append(npc_id)

    def remove_npc(self, npc_id: str) -> None:
        if npc_id in self.npcs_present:
            self.npcs_present.remove(npc_id)
