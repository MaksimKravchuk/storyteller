"""Actor — an NPC that speaks and acts in character."""

from __future__ import annotations

from typing import Any

from cast.actor_config import ENVELOPE_MODE_DEFAULT, format_past_memories
from cast.actor_tags import strip_trailing_tags
from cast.base_performer_class import BasePerformer, LLMJSONError
from cast.hostility import apply_llm_mood_update, format_hostile_actions_summary
from cast.schemas.actor_reply import ActorEnvelope, ActorReply
from knowledge.query import KnowledgeQueryEngine
from llm.message import Message, Role
from loguru import logger
from models.npc_card import NPCCard
from prompts.actor_prompts import get_actor_prompts

_MEMORY_LIMIT = 5
_FALLBACK_NARRATION = "..."
_SALVAGE_NARRATION_MAX = 500


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
        envelope_mode: bool = ENVELOPE_MODE_DEFAULT,
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
        ``context``: Optional; may contain ``location_name`` and
        ``is_npc_turn`` (set by ``NPCTurnResolver`` when the NPC is acting
        on its own turn rather than responding to the player).

        Returns an :class:`ActorReply` with the spoken text (or raw action
        JSON, in NPC-turn mode) and any names the NPC revealed during this
        turn. NPC-turn mode returns ``revealed_names=()`` — action JSON
        carries no name-reveal signal.
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
            self.set_context(past_memories=format_past_memories(past_memories))

        # Inject hostility context only when the NPC is actually inflamed, so
        # peaceful dialogue does not carry a spurious "you are in conflict" banner.
        if self.npc.hostility_level > 0 or self.npc.recent_hostile_actions:
            self.set_context(
                hostility_level=str(self.npc.hostility_level),
                recent_hostile_actions_summary=format_hostile_actions_summary(
                    self.npc.recent_hostile_actions,
                ),
            )

        if context.get("is_npc_turn"):
            return await self._act_npc_turn(input_data)

        self.set_context(output_mode_dialogue="1")
        envelope = await self._produce_envelope(input_data)

        # Store only the prose narration so multi-turn dialogue context stays clean.
        self._conversation.append(Message(role=Role.USER, body=input_data))
        self._conversation.append(Message(role=Role.ASSISTANT, body=envelope.narration))

        if envelope.mood:
            apply_llm_mood_update(self.npc, envelope.mood)
        if envelope.status:
            self.npc.physical_status = envelope.status

        return ActorReply(text=envelope.narration.strip(), revealed_names=tuple(envelope.revealed_names))

    def reset_conversation(self) -> None:
        """Clear conversation history (e.g. when player walks away)."""
        self._conversation.clear()

    async def _act_npc_turn(self, input_data: str) -> ActorReply:
        """Action-mode dispatch: raw action JSON in, no envelope, no conversation state.

        An autonomous turn is not dialogue — its output schema is
        ``action/type/target``, not the narration envelope — so we bypass
        the envelope parse, do not append to ``self._conversation``, and
        do not mutate ``npc.current_mood`` / ``npc.physical_status``. Those
        stay calibrated from the next dialogue turn. ``NPCTurnResolver``
        parses the returned ``ActorReply.text`` as the action JSON.
        """
        self.set_context(output_mode_action="1")
        raw = await self._send(input_data, conversation=[])
        return ActorReply(text=raw.strip(), revealed_names=())

    async def _produce_envelope(self, input_data: str) -> ActorEnvelope:
        """Call the envelope or legacy path, with a graceful fallback on LLM JSON failure.

        Without this fallback, three consecutive malformed LLM responses
        bubble an :class:`LLMJSONError` all the way to the web/telegram
        interface and surface as an opaque 500 — killing the scene on one
        bad batch of tokens.
        """
        dispatch = self._act_envelope if self._envelope_mode else self._act_legacy
        try:
            return await dispatch(input_data)
        except LLMJSONError as exc:
            logger.warning(
                "Actor envelope parse failed for NPC {} ({}): {}",
                self.npc.name,
                self.npc.uuid,
                exc,
            )
            salvaged = (exc.raw_response or "").strip()[:_SALVAGE_NARRATION_MAX]
            return ActorEnvelope(narration=salvaged or _FALLBACK_NARRATION)

    async def _act_envelope(self, input_data: str) -> ActorEnvelope:
        return await self._send_json(
            input_data,
            conversation=self._conversation,
            response_model=ActorEnvelope,
        )

    async def _act_legacy(self, input_data: str) -> ActorEnvelope:
        raw = await self._send(input_data, conversation=self._conversation)
        parsed = strip_trailing_tags(raw)
        return ActorEnvelope(
            narration=parsed.text,
            mood=parsed.mood,
            status=parsed.status,
            revealed_names=parsed.revealed,
        )
