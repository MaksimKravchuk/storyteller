from __future__ import annotations

from uuid import UUID

from models.base_model import StorytellerBase


class Character(StorytellerBase):
    """Base character model — used for both the player and NPCs.

    Core identity fields are required; appearance / personality fields
    are optional and filled in by the NPC generator when needed.
    """

    name: str
    biography: str = ""
    relationships: dict[str, str] = {}
    attributes: dict[str, int] = {}
    inventory: list[str] = []
    # Extended fields (populated by NPC generator)
    appearance: str = ""
    short_descriptor: str = ""
    personality_traits: list[str] = []
    occupation: str = ""
    speech_style: str = ""
    knowledge_scope: str = "local"
    location_id: UUID | None = None

    # --- Attribute helpers ---

    def update_attribute(self, attribute: str, attribute_value: int) -> None:
        self.attributes[attribute] = attribute_value

    def get_attribute(self, attribute: str, default: int = 0) -> int:
        return self.attributes.get(attribute, default)

    # --- Inventory helpers ---

    def add_item_to_inventory(self, inventory_item: str) -> None:
        self.inventory.append(inventory_item)

    def remove_item_from_inventory(self, inventory_item: str) -> None:
        if inventory_item in self.inventory:
            self.inventory.remove(inventory_item)
        else:
            raise ValueError(f"Item '{inventory_item}' not found in inventory.")
