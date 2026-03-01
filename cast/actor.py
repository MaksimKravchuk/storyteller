"""Actor — an NPC that speaks and acts in character."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from knowledge.query import KnowledgeQueryEngine
from llm.message import Message, Role
from models.npc_card import NPCCard
from prompts.actor_prompts import ACTOR_SYSTEM


class Actor(BasePerformer):
    """An NPC actor that responds to player interaction in character.

    Each Actor wraps a single ``NPCCard`` and has access to a filtered
    view of the knowledge graph through the ``KnowledgeQueryEngine``.
    Conversation history is maintained for multi-turn dialogue.
    """

    def __init__(
        self,
        *,
        llm_client: Any,
        npc: NPCCard,
        knowledge_query: KnowledgeQueryEngine,
    ):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=ACTOR_SYSTEM,
        )
        self.npc = npc
        self.knowledge_query = knowledge_query
        self._conversation: list[Message] = []

    async def act(self, input_data: str, context: dict) -> str:
        """Respond to a player interaction in character.

        ``input_data``: What the player said or did directed at this NPC.
        ``context``: May contain ``location_name``, ``game_state``,
                     ``character_names``.

        Returns the NPC's spoken response.
        """
        # Build knowledge context for this NPC
        game_state = context.get("game_state")
        current_time = game_state.game_clock if game_state else None

        accessible_knowledge = self.knowledge_query.get_context_for_npc(
            self.npc, topic_tags=None, current_time=current_time
        )

        # Format goals
        active_goals = [g for g in self.npc.goals if not g.completed]
        goals_text = "\n".join(
            f"- {g.description} (priority {g.priority})"
            for g in active_goals
        ) if active_goals else "No specific goals right now"

        # Format emotional attitudes
        character_names = context.get("character_names", {})
        attitudes_text = self._format_emotional_attitudes(character_names)

        self.set_context(
            npc_name=self.npc.name,
            npc_occupation=self.npc.occupation,
            location_name=context.get("location_name", "this place"),
            npc_biography=self.npc.biography,
            personality_traits=", ".join(self.npc.personality_traits),
            speech_style=self.npc.speech_style,
            npc_appearance=self.npc.appearance,
            npc_inventory=(
                ", ".join(self.npc.inventory)
                if self.npc.inventory
                else "nothing special"
            ),
            accessible_knowledge=accessible_knowledge,
            current_mood=self.npc.current_mood,
            npc_goals=goals_text,
            npc_secrets=(
                ", ".join(self.npc.secrets) if self.npc.secrets else "None"
            ),
            npc_fears=(
                ", ".join(self.npc.fears) if self.npc.fears else "None"
            ),
            npc_obligations=(
                ", ".join(self.npc.obligations)
                if self.npc.obligations
                else "None"
            ),
            emotional_attitudes=attitudes_text,
        )

        response = await self._send(
            input_data, conversation=self._conversation
        )

        # Track conversation for multi-turn dialogue
        self._conversation.append(
            Message(role=Role.USER, content=input_data)
        )
        self._conversation.append(
            Message(role=Role.ASSISTANT, content=response)
        )

        return response.strip()

    def reset_conversation(self) -> None:
        """Clear conversation history (e.g. when player walks away)."""
        self._conversation.clear()

    def _format_emotional_attitudes(
        self, character_names: dict[str, str]
    ) -> str:
        """Format emotional attitudes for prompt injection."""
        if not self.npc.emotional_attitudes:
            return "No strong feelings about anyone yet"

        lines: list[str] = []
        for char_id, emotions in self.npc.emotional_attitudes.items():
            char_name = character_names.get(char_id, char_id)
            emo_parts = [
                f"{k}={v:.1f}" for k, v in emotions.items() if abs(v) > 0.1
            ]
            if emo_parts:
                lines.append(f"- {char_name}: {', '.join(emo_parts)}")

        return "\n".join(lines) if lines else "No strong feelings about anyone yet"
