"""Actor — an NPC that speaks and acts in character."""

from __future__ import annotations

import re
from typing import Any

from cast.base_performer_class import BasePerformer
from knowledge.query import KnowledgeQueryEngine
from llm.message import Message, Role
from models.npc_card import NPCCard
from prompts.actor_prompts import ACTOR_SYSTEM

_MOOD_RE = re.compile(r"\n?\[MOOD:\s*(\w+)\]\s*$")
_STATUS_RE = re.compile(r"\n?\[STATUS:\s*([^\]]+)\]\s*$")


def _extract_mood(text: str) -> tuple[str, str | None]:
    """Strip a ``[MOOD: <word>]`` tag from the end of *text*.

    Returns ``(cleaned_text, mood)`` where *mood* is ``None``
    when no tag was found.
    """
    mood_match = _MOOD_RE.search(text)
    if mood_match:
        return text[: mood_match.start()], mood_match.group(1).lower()
    return text, None


def _extract_status(text: str) -> tuple[str, str | None]:
    """Strip a ``[STATUS: <description>]`` tag from the end of *text*.

    Returns ``(cleaned_text, status)`` where *status* is ``None``
    when no tag was found.  Supports multi-word values like
    ``wounded left arm``.
    """
    status_match = _STATUS_RE.search(text)
    if status_match:
        cleaned = status_match.group(1).strip().lower()
        return text[: status_match.start()], cleaned
    return text, None


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
        accessible_knowledge = self.knowledge_query.get_context_for_npc(self.npc, topic_tags=None)

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
            physical_status=self.npc.physical_status,
        )

        response = await self._send(input_data, conversation=self._conversation)

        # Extract tags — status first, then mood from cleaned text
        response, new_status = _extract_status(response)
        response, new_mood = _extract_mood(response)

        # Track conversation for multi-turn dialogue
        self._conversation.append(Message(role=Role.USER, body=input_data))
        self._conversation.append(Message(role=Role.ASSISTANT, body=response))

        if new_mood:
            self.npc.current_mood = new_mood
        if new_status:
            self.npc.physical_status = new_status

        return response.strip()

    def reset_conversation(self) -> None:
        """Clear conversation history (e.g. when player walks away)."""
        self._conversation.clear()
