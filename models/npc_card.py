from __future__ import annotations

from models.character import Character


class NPCCard(Character):
    """Extended character profile created by the NPC Generator.

    Adds runtime fields for conversation state, mood, and a method
    to serialise the card into a string for prompt injection.
    """

    def __init__(
        self,
        *,
        name: str,
        biography: str = "",
        appearance: str = "",
        occupation: str = "",
        personality_traits: list[str] | None = None,
        speech_style: str = "",
        knowledge_scope: str = "local",
        attributes: dict[str, int] | None = None,
        inventory: list[str] | None = None,
        location_id: str | None = None,
        relationships: dict[str, str] | None = None,
    ):
        super().__init__(
            name=name,
            biography=biography,
            relationships=relationships,
            attributes=attributes,
            inventory=inventory,
            appearance=appearance,
            personality_traits=personality_traits,
            occupation=occupation,
            speech_style=speech_style,
            knowledge_scope=knowledge_scope,
            location_id=location_id,
        )
        self.conversation_history: list[dict[str, str]] = []
        self.current_mood: str = "neutral"

    def to_prompt_context(self) -> str:
        """Serialise this NPC card into text for injection into a system prompt."""
        lines = [
            f"Name: {self.name}",
            f"Occupation: {self.occupation}",
            f"Appearance: {self.appearance}",
            f"Biography: {self.biography}",
            f"Personality: {', '.join(self.personality_traits)}",
            f"Speech style: {self.speech_style}",
            f"Knowledge scope: {self.knowledge_scope}",
            f"Current mood: {self.current_mood}",
        ]
        if self.inventory:
            lines.append(f"Inventory: {', '.join(self.inventory)}")
        if self.attributes:
            attrs = ", ".join(f"{k}={v}" for k, v in self.attributes.items())
            lines.append(f"Attributes: {attrs}")
        return "\n".join(lines)
