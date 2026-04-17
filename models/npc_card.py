from __future__ import annotations

from typing import TYPE_CHECKING

from models.character import Character

if TYPE_CHECKING:
    from models.game_state import GameState


def _format_attr(attr_name: str, attr_val: object) -> str:
    return "{0}={1}".format(attr_name, attr_val)


class NPCCard(Character):
    """Extended character profile created by the NPC Generator.

    Adds runtime fields for conversation state, mood, and a method
    to serialise the card into a string for prompt injection.
    """

    conversation_history: list[dict[str, str]] = []
    current_mood: str = "neutral"
    physical_status: str = "healthy"
    hostility_level: int = 0
    recent_hostile_actions: list[dict[str, str]] = []

    def label_for_player(self, game_state: GameState, role_fallback: str) -> str:
        """Return the label the player should see for this NPC.

        Three-branch rule shared by the Narrator (``npcs_present`` line)
        and the plan executor (``raw_outputs.new_npcs``):

        1. Player has been introduced (``uuid`` is in
           ``game_state.player.known_npcs``) → ``"Name (Occupation)"``.
        2. Card carries a ``short_descriptor`` → the descriptor verbatim.
        3. Neither → ``role_fallback`` — the ``SceneNPC.role`` tag or,
           for freshly-generated cards not yet in any scene, the
           card's own ``occupation``.
        """
        if self.uuid and self.uuid in game_state.player.known_npcs:
            if self.occupation:
                return "{0} ({1})".format(self.name, self.occupation)
            return self.name
        if self.short_descriptor:
            return self.short_descriptor
        return role_fallback

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
            f"Physical status: {self.physical_status}",
        ]
        if self.inventory:
            lines.append("Inventory: {0}".format(", ".join(self.inventory)))
        if self.attributes:
            attr_strs = [_format_attr(attr_name, attr_val) for attr_name, attr_val in self.attributes.items()]
            attrs = ", ".join(attr_strs)
            lines.append(f"Attributes: {attrs}")
        return "\n".join(lines)
