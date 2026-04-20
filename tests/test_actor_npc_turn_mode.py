"""Tests for Actor dispatch on ``is_npc_turn``.

The NPC autonomous-turn path must use a system prompt shaped for JSON
output, must not leak prior dialogue history into the action-mode call,
and must not pollute conversation state (so a later dialogue turn with
the same Actor starts cleanly). The dialogue path must stay untouched.
"""

from __future__ import annotations

import types
from unittest.mock import AsyncMock

import allure
import pytest

from cast.actor import Actor
from cast.schemas.actor_reply import ActorReply
from knowledge.graph import KnowledgeGraph
from knowledge.query import KnowledgeQueryEngine
from llm.message import LLMResponse, Role
from models.npc_card import NPCCard

_LOC_CONTEXT: types.MappingProxyType[str, str] = types.MappingProxyType({"location_name": "forum"})
_NPC_TURN_USER_PROMPT = 'It is Brutus\'s turn.\nRespond as JSON:\n{"action": "...", "type": "IDLE", "target": null}'


def _make_npc() -> NPCCard:
    npc = NPCCard(
        name="Brutus",
        occupation="former legionary",
        biography="A disgraced veteran.",
        personality_traits=["vengeful"],
        speech_style="terse",
        appearance="lean, scarred",
        inventory=["concealed pugio"],
    )
    npc.current_mood = "hostile"
    npc.physical_status = "healthy"
    return npc


def _make_actor(llm_client: AsyncMock) -> Actor:
    return Actor(
        llm_client=llm_client,
        npc=_make_npc(),
        knowledge_query=KnowledgeQueryEngine(KnowledgeGraph()),
    )


def _mock_llm(body: str = '{"action": "Brutus watches.", "type": "IDLE", "target": null}') -> AsyncMock:
    """Build an llm_client mock whose send_message records its kwargs and returns a fixed body."""
    client = AsyncMock()
    client.model = "test-model"
    client.send_message = AsyncMock(
        return_value=LLMResponse(body=body, model="test-model", usage={}),
    )
    return client


@allure.epic("NPC Interaction")
@allure.feature("Actor action-mode dispatch")
class TestActorNPCTurnModeSystemPrompt:
    @allure.story("System-prompt swap")
    @allure.title("is_npc_turn=True renders the action-mode system prompt — JSON directive, no dialogue tag rules")
    @pytest.mark.asyncio
    async def test_npc_turn_uses_action_system_prompt(self):
        client = _mock_llm()
        actor = _make_actor(client)

        await actor.execute(_NPC_TURN_USER_PROMPT, context={**_LOC_CONTEXT, "is_npc_turn": True})

        kwargs = client.send_message.await_args.kwargs
        system_prompt = kwargs["system_prompt"]
        assert "JSON object" in system_prompt
        assert "Output ONLY your spoken dialogue" not in system_prompt
        assert "[MOOD:" not in system_prompt
        assert "[REVEALED:" not in system_prompt

    @allure.story("System-prompt swap")
    @allure.title("is_npc_turn=False still renders the dialogue system prompt with its tag instructions")
    @pytest.mark.asyncio
    async def test_dialogue_turn_uses_dialogue_system_prompt(self):
        client = _mock_llm(body="Greetings, stranger.")
        actor = _make_actor(client)

        await actor.execute("hello", context=_LOC_CONTEXT)

        system_prompt = client.send_message.await_args.kwargs["system_prompt"]
        assert "Output ONLY your spoken dialogue" in system_prompt
        assert "[MOOD:" in system_prompt


@allure.epic("NPC Interaction")
@allure.feature("Actor action-mode dispatch")
class TestActorNPCTurnModeHistoryIsolation:
    @allure.story("Conversation isolation")
    @allure.title("NPC-turn calls do not pass prior dialogue history into the LLM message list")
    @pytest.mark.asyncio
    async def test_npc_turn_sends_single_message_with_no_history(self):
        client = _mock_llm()
        actor = _make_actor(client)
        # Seed a prior dialogue turn so there IS conversation history to leak.
        client.send_message.return_value = LLMResponse(body="Greetings.", model="test-model", usage={})
        await actor.execute("hello", context=_LOC_CONTEXT)
        client.send_message.return_value = LLMResponse(
            body='{"action": "Brutus watches.", "type": "IDLE", "target": null}',
            model="test-model",
            usage={},
        )

        await actor.execute(_NPC_TURN_USER_PROMPT, context={**_LOC_CONTEXT, "is_npc_turn": True})

        messages = client.send_message.await_args.kwargs["messages"]
        # Only the NPC-turn user message — no prior user/assistant dialogue pair.
        assert len(messages) == 1
        assert messages[0].role == Role.USER
        assert messages[0].body == _NPC_TURN_USER_PROMPT

    @allure.story("Conversation isolation")
    @allure.title("NPC-turn calls do not append to actor._conversation")
    @pytest.mark.asyncio
    async def test_npc_turn_does_not_grow_conversation(self):
        client = _mock_llm()
        actor = _make_actor(client)

        await actor.execute(_NPC_TURN_USER_PROMPT, context={**_LOC_CONTEXT, "is_npc_turn": True})

        assert actor._conversation == []

    @allure.story("Conversation isolation")
    @allure.title("Dialogue turns after an NPC turn still grow actor._conversation as normal")
    @pytest.mark.asyncio
    async def test_dialogue_after_npc_turn_grows_conversation(self):
        client = _mock_llm()
        actor = _make_actor(client)

        await actor.execute(_NPC_TURN_USER_PROMPT, context={**_LOC_CONTEXT, "is_npc_turn": True})
        client.send_message.return_value = LLMResponse(body="Greetings.", model="test-model", usage={})
        await actor.execute("hello", context=_LOC_CONTEXT)

        assert len(actor._conversation) == 2


@allure.epic("NPC Interaction")
@allure.feature("Actor action-mode dispatch")
class TestActorNPCTurnModeReplyShape:
    @allure.story("Reply shape")
    @allure.title("NPC-turn reply returns the raw LLM body stripped, with empty revealed_names")
    @pytest.mark.asyncio
    async def test_npc_turn_returns_raw_stripped_reply(self):
        raw_json = '{"action": "Brutus watches.", "type": "IDLE", "target": null}'
        client = _mock_llm(body=f"  {raw_json}\n")
        actor = _make_actor(client)

        reply = await actor.execute(_NPC_TURN_USER_PROMPT, context={**_LOC_CONTEXT, "is_npc_turn": True})

        assert isinstance(reply, ActorReply)
        assert reply.text == raw_json
        assert reply.revealed_names == ()

    @allure.story("Reply shape")
    @allure.title("NPC-turn branch does not mutate npc.current_mood or npc.physical_status from the raw output")
    @pytest.mark.asyncio
    async def test_npc_turn_does_not_mutate_npc_state_from_tags(self):
        # Even if the LLM mis-emits a trailing [MOOD:] tag, the action-mode
        # branch must not interpret it as a mood shift — mood lives in the
        # dialogue path.
        body = '{"action": "...", "type": "IDLE", "target": null}\n[MOOD: calm]'
        client = _mock_llm(body=body)
        actor = _make_actor(client)

        await actor.execute(_NPC_TURN_USER_PROMPT, context={**_LOC_CONTEXT, "is_npc_turn": True})

        assert actor.npc.current_mood == "hostile"
        assert actor.npc.physical_status == "healthy"


@allure.epic("NPC Interaction")
@allure.feature("Actor action-mode dispatch")
class TestActorTemplateSwapIsNotSticky:
    @allure.story("Template swap hygiene")
    @allure.title("After an NPC-turn call, the Actor's system_prompt_template is restored to the dialogue template")
    @pytest.mark.asyncio
    async def test_template_restored_after_npc_turn(self):
        client = _mock_llm()
        actor = _make_actor(client)

        await actor.execute(_NPC_TURN_USER_PROMPT, context={**_LOC_CONTEXT, "is_npc_turn": True})

        assert actor.system_prompt_template is actor._dialogue_template

    @allure.story("Template swap hygiene")
    @allure.title("If the LLM call raises, the dialogue template is still restored before the exception propagates")
    @pytest.mark.asyncio
    async def test_template_restored_when_send_raises(self):
        client = _mock_llm()
        client.send_message.side_effect = RuntimeError("LLM timeout")
        actor = _make_actor(client)

        with pytest.raises(RuntimeError):
            await actor.execute(_NPC_TURN_USER_PROMPT, context={**_LOC_CONTEXT, "is_npc_turn": True})

        assert actor.system_prompt_template is actor._dialogue_template

    @allure.story("Template swap hygiene")
    @allure.title("asyncio.CancelledError still restores the dialogue template and propagates")
    @pytest.mark.asyncio
    async def test_template_restored_on_cancellation(self):
        import asyncio

        client = _mock_llm()
        client.send_message.side_effect = asyncio.CancelledError()
        actor = _make_actor(client)

        with pytest.raises(asyncio.CancelledError):
            await actor.execute(_NPC_TURN_USER_PROMPT, context={**_LOC_CONTEXT, "is_npc_turn": True})

        assert actor.system_prompt_template is actor._dialogue_template

    @allure.story("Template swap hygiene")
    @allure.title("A dialogue call after an NPC turn renders the dialogue prompt, not the action one")
    @pytest.mark.asyncio
    async def test_dialogue_after_npc_turn_uses_dialogue_template(self):
        client = _mock_llm()
        actor = _make_actor(client)

        await actor.execute(_NPC_TURN_USER_PROMPT, context={**_LOC_CONTEXT, "is_npc_turn": True})
        client.send_message.return_value = LLMResponse(body="Greetings.", model="test-model", usage={})
        await actor.execute("hello", context=_LOC_CONTEXT)

        # The most recent send_message used the dialogue system prompt.
        system_prompt = client.send_message.await_args.kwargs["system_prompt"]
        assert "Output ONLY your spoken dialogue" in system_prompt
