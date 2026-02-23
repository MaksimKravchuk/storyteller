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
        ``context``: Optional; may contain ``location_name``.

        Returns the NPC's spoken response.
        """
        # Build knowledge context for this NPC
        accessible_knowledge = self.knowledge_query.get_context_for_npc(
            self.npc, topic_tags=None
        )

        self.set_context(
            npc_name=self.npc.name,
            npc_occupation=self.npc.occupation,
            location_name=context.get("location_name", "this place"),
            npc_biography=self.npc.biography,
            personality_traits=", ".join(self.npc.personality_traits),
            speech_style=self.npc.speech_style,
            npc_appearance=self.npc.appearance,
            npc_inventory=", ".join(self.npc.inventory) if self.npc.inventory else "nothing special",
            accessible_knowledge=accessible_knowledge,
            current_mood=self.npc.current_mood,
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
