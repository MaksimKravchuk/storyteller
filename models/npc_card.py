from __future__ import annotations

from dataclasses import dataclass, field

from models.character import Character


def _format_attr(attr_name: str, attr_val: object) -> str:
    return "{0}={1}".format(attr_name, attr_val)


@dataclass(kw_only=True)
class NPCCard(Character):
    """Extended character profile created by the NPC Generator.

    Adds runtime fields for conversation state, mood, and a method
    to serialise the card into a string for prompt injection.
    """

    conversation_history: list[dict[str, str]] = field(default_factory=list)
    current_mood: str = "neutral"

    def to_prompt_context(self) -> str:
        """Serialise this NPC card into text for injection into a system prompt."""
        lines = [
            f"Name: {self.name}",
            f"Occupation: {self.occupation}",
            f"Appearance: {self.appearance}",
            f"Biography: {self.biography}",
            "Personality: {0}".format(", ".join(self.personality_traits)),
            f"Speech style: {self.speech_style}",
            f"Knowledge scope: {self.knowledge_scope}",
            f"Current mood: {self.current_mood}",
        ]
        if self.inventory:
            lines.append("Inventory: {0}".format(", ".join(self.inventory)))
        if self.attributes:
            attr_strs = [_format_attr(attr_name, attr_val) for attr_name, attr_val in self.attributes.items()]
            attrs = ", ".join(attr_strs)
            lines.append(f"Attributes: {attrs}")
        return "\n".join(lines)
