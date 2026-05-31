"""Actor — an NPC that speaks and acts in character."""

from __future__ import annotations

from typing import Any

from cast.actor_config import format_past_memories, goal_prompt_vars
from cast.actor_memory import format_accessible_knowledge, select_actor_memories
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
_OPTIONAL_CONTEXT_KEYS = (
    "past_memories",
    "hostility_level",
    "recent_hostile_actions_summary",
    "goal_kind",
    "goal_target",
    "goal_turns_pursued",
    "goal_description",
    "goal_last_action",
    "goal_progress_notes",
)


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
        prompts = get_actor_prompts(language)
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=prompts.system_dialogue,
        )
        self._system_dialogue = prompts.system_dialogue
        self._system_action = prompts.system_action
        self.npc = npc
        self.knowledge_query = knowledge_query
        self._conversation: list[Message] = []
        self.set_context(language=language)

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
        accessible_knowledge = format_accessible_knowledge(self.knowledge_query, self.npc)

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

        _apply_optional_sections(self, context)

        if context.get("is_npc_turn"):
            return await self._act_npc_turn(input_data)

        self.system_prompt_template = self._system_dialogue
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

    def clear_optional_context(self) -> None:
        """Drop optional prompt vars before rendering the next turn."""
        for context_key in _OPTIONAL_CONTEXT_KEYS:
            self._system_prompt_vars.pop(context_key, None)

    async def _act_npc_turn(self, input_data: str) -> ActorReply:
        """Action-mode dispatch: raw action JSON in, no envelope, no conversation state.

        An autonomous turn is not dialogue — its output schema is
        ``action/type/target``, not the narration envelope — so we bypass
        the envelope parse, do not append to ``self._conversation``, and
        do not mutate ``npc.current_mood`` / ``npc.physical_status``. Those
        stay calibrated from the next dialogue turn. ``NPCTurnResolver``
        parses the returned ``ActorReply.text`` as the action JSON.
        """
        self.system_prompt_template = self._system_action
        raw = await self._send(input_data, conversation=[])
        return ActorReply(text=raw.strip(), revealed_names=())

    async def _produce_envelope(self, input_data: str) -> ActorEnvelope:
        """Call the LLM envelope path, with a graceful fallback on JSON failure.

        Without this fallback, three consecutive malformed LLM responses
        bubble an :class:`LLMJSONError` all the way to the web interface
        and surface as an opaque 500 — killing the scene on one
        bad batch of tokens.
        """
        try:
            return await self._send_json(
                input_data,
                conversation=self._conversation,
                response_model=ActorEnvelope,
            )
        except LLMJSONError as exc:
            logger.warning(
                "Actor envelope parse failed for NPC {} ({}): {}",
                self.npc.name,
                self.npc.uuid,
                exc,
            )
            salvaged = (exc.raw_response or "").strip()[:_SALVAGE_NARRATION_MAX]
            return ActorEnvelope(narration=salvaged or _FALLBACK_NARRATION)


def _apply_optional_sections(actor: Actor, context: dict) -> None:
    """Wire context vars for the optional Actor prompt sections.

    Each section (past memories, hostility banner, standing goal) is
    gated so peaceful, goal-less NPCs see no spurious banners — the
    PromptTemplate omits optional sections whose required vars were
    not set on the context.

    Most optional wiring lives outside the :class:`Actor` class so the
    prompt-selection logic stays isolated from the performer control flow.
    """
    actor.clear_optional_context()
    past_memories = select_actor_memories(actor.npc, actor.knowledge_query, context, limit=_MEMORY_LIMIT)
    if past_memories:
        actor.set_context(past_memories=format_past_memories(past_memories))
    if actor.npc.hostility_level > 0 or actor.npc.recent_hostile_actions:
        actor.set_context(
            hostility_level=str(actor.npc.hostility_level),
            recent_hostile_actions_summary=format_hostile_actions_summary(actor.npc.recent_hostile_actions),
        )
    goal_vars = goal_prompt_vars(actor.npc, context.get("goal_target_name"))
    if goal_vars is not None:
        actor.set_context(**goal_vars)
