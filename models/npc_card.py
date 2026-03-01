from __future__ import annotations

from dataclasses import dataclass, field

from models.character import Character


@dataclass
class Goal:
    """An NPC's active goal."""

    description: str
    priority: int = 5  # 1-10, higher = more important
    related_check: str = ""  # CheckType value, e.g. "persuasion"
    target_id: str | None = None  # UUID of target character/location
    progress: float = 0.0  # 0.0-1.0
    completed: bool = False


class NPCCard(Character):
    """Extended character profile created by the NPC Generator.

    Adds runtime fields for conversation state, mood, goals, secrets,
    emotional attitudes, and a method to serialise the card into a
    string for prompt injection.
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
        # Autonomy fields
        goals: list[Goal] | None = None,
        secrets: list[str] | None = None,
        fears: list[str] | None = None,
        obligations: list[str] | None = None,
        importance: int = 5,
        # Emotional attitudes: character UUID -> {emotion: value}
        emotional_attitudes: dict[str, dict[str, float]] | None = None,
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

        # Autonomy
        self.goals: list[Goal] = goals or []
        self.secrets: list[str] = secrets or []
        self.fears: list[str] = fears or []
        self.obligations: list[str] = obligations or []
        self.importance: int = importance  # 1-10, determines autonomy tier

        # Maps character UUID -> {trust, fear, gratitude, resentment,
        # respect, contempt, affection, suspicion} with values -1.0 to 1.0
        self.emotional_attitudes: dict[str, dict[str, float]] = (
            emotional_attitudes or {}
        )

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
        if self.goals:
            active = [g for g in self.goals if not g.completed]
            if active:
                goals_str = "; ".join(
                    f"{g.description} (priority {g.priority})" for g in active
                )
                lines.append(f"Goals: {goals_str}")
        if self.secrets:
            lines.append(f"Secrets: {', '.join(self.secrets)}")
        if self.fears:
            lines.append(f"Fears: {', '.join(self.fears)}")
        if self.obligations:
            lines.append(f"Obligations: {', '.join(self.obligations)}")
        return "\n".join(lines)
