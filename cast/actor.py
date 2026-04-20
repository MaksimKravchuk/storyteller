"""Actor — an NPC that speaks and acts in character.

The Actor has two distinct call modes, selected by ``context["is_npc_turn"]``:

* **Dialogue** (default): the NPC replies to a player utterance as free
  text, optionally emitting trailing ``[MOOD]`` / ``[STATUS]`` /
  ``[REVEALED]`` tags. Conversation history is maintained across turns
  so multi-turn exchanges stay coherent.
* **Autonomous action** (``is_npc_turn=True``): the NPC returns a
  single JSON object describing one in-character action. The
  action-mode system template is used, no conversation history is
  passed or stored, and trailing tags are neither emitted nor parsed —
  ``cast.npc_turn`` owns JSON parsing downstream.
"""

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
from prompts.actor_prompts import get_actor_prompts

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
        language: str = "English",
    ):
        bundle = get_actor_prompts(language)
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=bundle.system,
        )
        self._dialogue_template = bundle.system
        self._action_template = bundle.system_action
        self.npc = npc
        self.knowledge_query = knowledge_query
        self._conversation: list[Message] = []
        self.set_context(language=language)

    async def act(self, input_data: str, context: dict) -> ActorReply:
        """Respond to a player interaction or drive an autonomous turn.

        ``input_data``: player utterance (dialogue mode) or the NPC-turn
        JSON-schema prompt built in :mod:`cast.npc_turn`.
        ``context``: may carry ``location_name`` and, for autonomous
        turns, ``is_npc_turn=True``.
        """
        self._populate_character_context(context)
        if context.get("is_npc_turn"):
            return await self._act_npc_turn(input_data)
        return await self._act_dialogue(input_data)

    def reset_conversation(self) -> None:
        """Clear conversation history."""
        self._conversation.clear()

    def _populate_character_context(self, context: dict) -> None:
        """Set every system-prompt variable this Actor's templates need.

        Both the dialogue and action-mode templates share the same
        character-context sections (identity, inventory, knowledge,
        memory, hostility), so the same context block feeds both.
        """
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

    async def _act_dialogue(self, input_data: str) -> ActorReply:
        """Run the dialogue path — free-text reply, trailing tags parsed, conversation retained."""
        raw = await self._send(input_data, conversation=self._conversation)
        parsed = strip_trailing_tags(raw)

        self._conversation.append(Message(role=Role.USER, body=input_data))
        self._conversation.append(Message(role=Role.ASSISTANT, body=parsed.text))

        if parsed.mood:
            apply_llm_mood_update(self.npc, parsed.mood)
        if parsed.status:
            self.npc.physical_status = parsed.status

        return ActorReply(text=parsed.text.strip(), revealed_names=tuple(parsed.revealed))

    async def _act_npc_turn(self, input_data: str) -> ActorReply:
        """Run the autonomous-action path — JSON reply, no conversation, no tags.

        The action-mode system template is swapped in for a single
        ``_send`` call, then restored so a subsequent dialogue turn on
        the same Actor starts clean. The restore path catches
        :exc:`BaseException` so cancellation and shutdown signals do
        not leave the Actor pinned to the action template — the next
        dialogue turn must not render a JSON-only system prompt.
        """
        self.system_prompt_template = self._action_template
        try:
            raw = await self._send(input_data)
        except BaseException:
            self.system_prompt_template = self._dialogue_template
            raise
        self.system_prompt_template = self._dialogue_template
        return ActorReply(text=raw.strip(), revealed_names=())
