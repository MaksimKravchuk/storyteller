from __future__ import annotations

from models.base_model import BaseModel


class Character(BaseModel):
    """Base character model — used for both the player and NPCs.

    Core identity fields are required; appearance / personality fields
    are optional and filled in by the NPC generator when needed.
    """

    def __init__(
        self,
        name: str,
        biography: str = "",
        relationships: dict[str, str] | None = None,
        attributes: dict[str, int] | None = None,
        inventory: list[str] | None = None,
        # Extended fields (populated by NPC generator)
        appearance: str = "",
        personality_traits: list[str] | None = None,
        occupation: str = "",
        speech_style: str = "",
        knowledge_scope: str = "local",
        location_id: str | None = None,
    ):
        super().__init__()
        self.name: str = name
        self.biography: str = biography
        self.relationships: dict[str, str] = relationships or {}
        self.attributes: dict[str, int] = attributes or {}
        self.inventory: list[str] = inventory or []
        # Extended
        self.appearance: str = appearance
        self.personality_traits: list[str] = personality_traits or []
        self.occupation: str = occupation
        self.speech_style: str = speech_style
        self.knowledge_scope: str = knowledge_scope  # "local"/"city"/"region"/"country"/"world"
        self.location_id: str | None = location_id

    # --- Relationship helpers ---

    def add_relationship(self, other_character_id: str, relationship_type: str) -> None:
        self.relationships[other_character_id] = relationship_type

    # --- Attribute helpers ---

    def update_attribute(self, attribute: str, value: int) -> None:
        self.attributes[attribute] = value

    def get_attribute(self, attribute: str, default: int = 0) -> int:
        return self.attributes.get(attribute, default)

    # --- Inventory helpers ---

    def add_item_to_inventory(self, item: str) -> None:
        self.inventory.append(item)

    def remove_item_from_inventory(self, item: str) -> None:
        if item in self.inventory:
            self.inventory.remove(item)
        else:
            raise ValueError(f"Item '{item}' not found in inventory.")

    def talk(self) -> str:
        return f"{self.name} says: Hello!"
