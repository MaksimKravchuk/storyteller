"""Actor — an NPC that speaks and acts in character."""

from __future__ import annotations

import os
from typing import Any

from cast.actor_tags import strip_trailing_tags
from cast.base_performer_class import BasePerformer
from cast.hostility import apply_llm_mood_update, format_hostile_actions_summary
from cast.schemas.actor_reply import ActorEnvelope, ActorReply
from knowledge.node import KnowledgeNode
from knowledge.query import KnowledgeQueryEngine
from llm.message import Message, Role
from models.npc_card import NPCCard
from prompts.actor_prompts import get_actor_prompts

_MEMORY_LIMIT = 5
_MEMORY_TEXT_MAX_CHARS = 200
# Evaluated once at module import; tests override via the constructor parameter.
_ENVELOPE_MODE_DEFAULT: bool = os.environ.get("ACTOR_ENVELOPE_MODE", "true").lower() != "false"


def _format_past_memories(memories: list[KnowledgeNode]) -> str:
    """Render a newline-joined bullet list of memory texts, truncated for prompt safety."""
    lines: list[str] = []
    for memory in memories:
        text = memory.text
        if len(text) > _MEMORY_TEXT_MAX_CHARS:
            text = "{0}...".format(text[: _MEMORY_TEXT_MAX_CHARS - 3])
        lines.append("- {0}".format(text))
    return "\n".join(lines)


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
        language: str = "English",
        envelope_mode: bool = _ENVELOPE_MODE_DEFAULT,
    ):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=get_actor_prompts(language).system,
        )
        self.npc = npc
        self.knowledge_query = knowledge_query
        self._conversation: list[Message] = []
        self.set_context(language=language)
        self._envelope_mode = envelope_mode

    async def act(self, input_data: str, context: dict) -> ActorReply:
        """Respond to a player interaction in character.

        ``input_data``: What the player said or did directed at this NPC.
        ``context``: Optional; may contain ``location_name``.

        Returns an :class:`ActorReply` with the spoken text and any
        names the NPC revealed during this turn.
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

        # Inject recent long-term memories about the player, when any exist.
        # We deliberately avoid calling set_context(past_memories="") when there
        # are none — the PromptTemplate skips optional sections only when their
        # required vars are MISSING from kwargs, not when they are empty strings.
        past_memories = self.knowledge_query.get_memories_about(self.npc.uuid, limit=_MEMORY_LIMIT)
        if past_memories:
            self.set_context(past_memories=_format_past_memories(past_memories))

        # Inject hostility context only when the NPC is actually inflamed, so
        # peaceful dialogue does not carry a spurious "you are in conflict" banner.
        if self.npc.hostility_level > 0 or self.npc.recent_hostile_actions:
            self.set_context(
                hostility_level=str(self.npc.hostility_level),
                recent_hostile_actions_summary=format_hostile_actions_summary(
                    self.npc.recent_hostile_actions,
                ),
            )

        if self._envelope_mode:
            narration, mood, status, revealed = await self._act_envelope(input_data)
        else:
            narration, mood, status, revealed = await self._act_legacy(input_data)

        # Store only the prose narration so multi-turn dialogue context stays clean.
        self._conversation.append(Message(role=Role.USER, body=input_data))
        self._conversation.append(Message(role=Role.ASSISTANT, body=narration))

        if mood:
            apply_llm_mood_update(self.npc, mood)
        if status:
            self.npc.physical_status = status

        return ActorReply(text=narration.strip(), revealed_names=tuple(revealed))

    async def _act_envelope(self, input_data: str) -> tuple[str, str | None, str | None, list[str]]:
        envelope = await self._send_json(
            input_data,
            conversation=self._conversation,
            response_model=ActorEnvelope,
        )
        return envelope.narration, envelope.mood, envelope.status, envelope.revealed_names

    async def _act_legacy(self, input_data: str) -> tuple[str, str | None, str | None, list[str]]:
        raw = await self._send(input_data, conversation=self._conversation)
        parsed = strip_trailing_tags(raw)
        return parsed.text, parsed.mood, parsed.status, parsed.revealed

    def reset_conversation(self) -> None:
        """Clear conversation history (e.g. when player walks away)."""
        self._conversation.clear()
