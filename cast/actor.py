"""Actor — an NPC that speaks and acts in character."""

from __future__ import annotations

from typing import Any

from cast.actor_tags import strip_trailing_tags
from cast.base_performer_class import BasePerformer
from cast.hostility import apply_llm_mood_update, format_hostile_actions_summary
from cast.schemas.actor_reply import ActorReply
from knowledge.node import KnowledgeNode
from knowledge.query import KnowledgeQueryEngine
from llm.message import Message, Role
from models.npc_card import NPCCard
from prompts.actor_prompts import ACTOR_SYSTEM

_MEMORY_LIMIT = 5
_MEMORY_TEXT_MAX_CHARS = 200


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
    ):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=ACTOR_SYSTEM,
        )
        self.npc = npc
        self.knowledge_query = knowledge_query
        self._conversation: list[Message] = []

    async def act(self, input_data: str, context: dict) -> ActorReply:
        """Respond to a player interaction in character.

        ``input_data``: What the player said or did directed at this NPC.
        ``context``: Optional; may contain ``location_name``.

        Returns an :class:`ActorReply` carrying the tag-stripped spoken
        text plus any ``[REVEALED: ...]`` tokens the Actor emitted.
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

        raw = await self._send(input_data, conversation=self._conversation)
        # Strip trailing inline tags in any order (MOOD / STATUS / REVEALED).
        parsed = strip_trailing_tags(raw)

        # Track conversation for multi-turn dialogue
        self._conversation.append(Message(role=Role.USER, body=input_data))
        self._conversation.append(Message(role=Role.ASSISTANT, body=parsed.text))

        if parsed.mood:
            apply_llm_mood_update(self.npc, parsed.mood)
        if parsed.status:
            self.npc.physical_status = parsed.status

        return ActorReply(text=parsed.text.strip(), revealed_names=tuple(parsed.revealed))

    def reset_conversation(self) -> None:
        """Clear conversation history (e.g. when player walks away)."""
        self._conversation.clear()
