from __future__ import annotations

from typing import TYPE_CHECKING

from models.character import Character

if TYPE_CHECKING:
    from models.game_state import GameState


def _format_attr(attr_name: str, attr_val: object) -> str:
    return "{0}={1}".format(attr_name, attr_val)


def _dedup_preserving_order(names: list[str]) -> list[str]:
    """Drop empty/whitespace entries and duplicates while keeping order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for raw in names:
        stripped = raw.strip() if raw else raw
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        deduped.append(stripped)
    return deduped


def _introduced_aliases(name: str, occupation: str) -> list[str]:
    """Build the alias list for an introduced NPC.

    Primary element keeps the legacy ``"Name (Occupation)"`` shape so
    ``label_for_player`` reads the same. The bare name and
    ``"the <occupation>"`` follow for narrator variation and post-match
    coverage.
    """
    if occupation:
        return [
            "{0} ({1})".format(name, occupation),
            name,
            "the {0}".format(occupation),
        ]
    return [name]


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
        """Return the primary label the player should see for this NPC.

        Thin accessor over :meth:`known_names_for_player` — picks the
        first (primary) alias. Preserves the historical shape:
        ``"Name (Occupation)"`` when introduced, else the descriptor,
        else the role fallback.
        """
        return self.known_names_for_player(game_state, role_fallback)[0]

    def known_names_for_player(self, game_state: GameState, role_fallback: str) -> list[str]:
        """Return every alias the player may read for this NPC this turn.

        The Narrator picks among them for natural variation; the
        entity-markup post-match wraps any of them as a hit for the
        same entity id.

        1. Introduced (``uuid in game_state.player.known_npcs``):
           ``[<Name>]`` plus ``"the <occupation>"`` when occupation is
           set. Also keeps the combined ``"Name (Occupation)"`` form as
           the primary element so ``label_for_player`` is unchanged.
        2. Unknown, ``short_descriptor`` set: ``[short_descriptor]``.
        3. Neither: ``[role_fallback]``.
        """
        if self.uuid and self.uuid in game_state.player.known_npcs:
            return _dedup_preserving_order(_introduced_aliases(self.name, self.occupation))
        if self.short_descriptor:
            return [self.short_descriptor]
        return [role_fallback]

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
