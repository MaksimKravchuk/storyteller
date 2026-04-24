"""Tests for the Actor revealed-names envelope field.

Covers three layers:

* ``Actor.act`` end-to-end on the envelope path — verifies the returned
  :class:`ActorReply` carries the revealed tokens from the JSON envelope
  and the spoken text is the ``narration`` field.
* ``Actor.act`` on the legacy rollback path (``envelope_mode=False``) —
  pins the trailing-tag parser so the ``ACTOR_ENVELOPE_MODE=false`` lever
  can't silently rot.
* The LLM-client integration boundary — exercises the real
  ``_send_json`` decode/validate/retry chain end-to-end, which the
  ``AsyncMock(_send_json)`` tests below intentionally bypass.

Pure regex-unit tests for the legacy tag extractor live in
``tests/test_legacy_actor_tags.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.actor import Actor
from cast.schemas.actor_reply import ActorEnvelope, ActorReply
from knowledge.graph import KnowledgeGraph
from knowledge.query import KnowledgeQueryEngine
from llm.message import LLMResponse
from models.npc_card import NPCCard
from prompts.actor_prompts import ACTOR_SYSTEM

_LOC_KEY = "location_name"


def _make_actor(*, envelope_mode: bool = True) -> tuple[Actor, NPCCard]:
    npc = NPCCard(name="Marcus", occupation="legionary")
    actor = Actor(
        llm_client=AsyncMock(),
        npc=npc,
        knowledge_query=KnowledgeQueryEngine(KnowledgeGraph()),
        envelope_mode=envelope_mode,
    )
    return actor, npc


def _llm_body(body: str) -> LLMResponse:
    return LLMResponse(body=body, model="test", usage={})


@allure.epic("NPC Interaction")
@allure.feature("Action-mode NPC turn")
class TestActorActNPCTurnMode:
    """``Actor.act`` respects ``context['is_npc_turn']`` by feeding the
    action-mode system prompt and returning the raw action JSON — no
    envelope parse, no conversation persistence, no mood/status mutation.
    """

    @allure.story("Action-mode dispatch")
    @allure.title("is_npc_turn context flag routes through _send with the action-mode system prompt")
    @pytest.mark.asyncio
    async def test_npc_turn_uses_action_mode_prompt(self):
        actor, npc = _make_actor()
        stub_raw = '{"action": "Brutus grips the pugio.", "type": "IDLE", "target": null}'
        actor._send = AsyncMock(return_value=stub_raw)  # type: ignore[method-assign]

        reply = await actor.act("It is Brutus's turn.", {_LOC_KEY: "taberna", "is_npc_turn": True})

        assert isinstance(reply, ActorReply)
        assert reply.text == stub_raw
        assert reply.revealed_names == ()

    @allure.story("Action-mode dispatch")
    @allure.title("Action-mode call bypasses the envelope path and does not touch conversation state")
    @pytest.mark.asyncio
    async def test_npc_turn_skips_envelope_and_conversation(self):
        actor, npc = _make_actor()
        stub_raw = '{"action": "watches the merchant", "type": "IDLE", "target": null}'
        actor._send = AsyncMock(return_value=stub_raw)  # type: ignore[method-assign]
        envelope_guard = AsyncMock(side_effect=AssertionError("_send_json must not run in NPC-turn mode"))
        actor._send_json = envelope_guard  # type: ignore[method-assign]

        await actor.act("Marcus sits across the room.", {_LOC_KEY: "taberna", "is_npc_turn": True})

        assert actor._conversation == []

    @allure.story("Action-mode dispatch")
    @allure.title("Action-mode sets the output_mode_action gate var on the system-prompt context")
    @pytest.mark.asyncio
    async def test_npc_turn_sets_action_mode_gate_var(self):
        actor, _ = _make_actor()
        actor._send = AsyncMock(  # type: ignore[method-assign]
            return_value='{"action": "stands watch", "type": "IDLE", "target": null}',
        )

        await actor.act("Turn advances.", {_LOC_KEY: "taberna", "is_npc_turn": True})

        assert actor._system_prompt_vars.get("output_mode_action") == "1"
        assert "output_mode_dialogue" not in actor._system_prompt_vars

        rendered = ACTOR_SYSTEM.render(**actor._system_prompt_vars)
        assert "ATTACK|TALK|MOVE|IDLE|STEALTH|PERSUADE|DECEIVE|INTIMIDATE" in rendered
        assert '"narration"' not in rendered
        assert '"revealed_names"' not in rendered

    @allure.story("Action-mode dispatch")
    @allure.title("NPC-turn after dialogue does not render both output sections — only action schema appears")
    @pytest.mark.asyncio
    async def test_npc_turn_after_dialogue_clears_dialogue_gate(self):
        """Regression: cumulative _system_prompt_vars kept output_mode_dialogue from the
        preceding dialogue call, so both output sections rendered.  The LLM then followed
        the dialogue schema and returned envelope JSON, parsed as IDLE by NPCTurnResolver."""
        actor, _ = _make_actor()

        # Simulate a preceding dialogue turn (sets output_mode_dialogue="1")
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="Aye.", revealed_names=[]),
        )
        await actor.act("Tell me your name.", {_LOC_KEY: "taberna"})

        assert "output_mode_dialogue" in actor._system_prompt_vars

        # Now an NPC autonomous turn runs on the same Actor instance
        actor._send = AsyncMock(  # type: ignore[method-assign]
            return_value='{"action": "draws sword", "type": "ATTACK", "target": "player"}',
        )
        await actor.act("Turn advances.", {_LOC_KEY: "taberna", "is_npc_turn": True})

        assert "output_mode_dialogue" not in actor._system_prompt_vars
        assert actor._system_prompt_vars.get("output_mode_action") == "1"

        rendered = ACTOR_SYSTEM.render(**actor._system_prompt_vars)
        assert '"narration"' not in rendered
        assert "ATTACK|TALK|MOVE|IDLE|STEALTH|PERSUADE|DECEIVE|INTIMIDATE" in rendered

    @allure.story("Action-mode dispatch")
    @allure.title("Dialogue after NPC-turn does not render both output sections — only envelope schema appears")
    @pytest.mark.asyncio
    async def test_dialogue_after_npc_turn_clears_action_gate(self):
        """Reverse-direction regression: output_mode_action from a prior NPC-turn call
        must be cleared when a subsequent dialogue call runs on the same Actor instance."""
        actor, _ = _make_actor()

        # Simulate a preceding NPC autonomous turn (sets output_mode_action="1")
        actor._send = AsyncMock(  # type: ignore[method-assign]
            return_value='{"action": "stands watch", "type": "IDLE", "target": null}',
        )
        await actor.act("Turn advances.", {_LOC_KEY: "taberna", "is_npc_turn": True})

        assert "output_mode_action" in actor._system_prompt_vars

        # Now a dialogue turn runs on the same Actor instance
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="Aye.", revealed_names=[]),
        )
        await actor.act("Tell me your name.", {_LOC_KEY: "taberna"})

        assert "output_mode_action" not in actor._system_prompt_vars
        assert actor._system_prompt_vars.get("output_mode_dialogue") == "1"

        rendered = ACTOR_SYSTEM.render(**actor._system_prompt_vars)
        assert '"narration"' in rendered
        assert "ATTACK|TALK|MOVE|IDLE|STEALTH|PERSUADE|DECEIVE|INTIMIDATE" not in rendered


@allure.epic("NPC Interaction")
@allure.feature("Revealed names envelope field")
class TestActorActReturnsActorReply:
    @allure.story("ActorReply return type")
    @allure.title("Actor.act returns an ActorReply whose revealed_names carries tokens from the JSON envelope")
    @pytest.mark.asyncio
    async def test_act_returns_actor_reply_with_tokens(self):
        actor, _ = _make_actor()
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="I am Marcus.", revealed_names=["self"]),
        )

        reply = await actor.act("who are you?", {_LOC_KEY: "forum"})

        assert isinstance(reply, ActorReply)
        assert reply.revealed_names == ("self",)
        assert reply.text == "I am Marcus."

    @allure.story("ActorReply return type")
    @allure.title("Actor.act returns an ActorReply with an empty revealed_names when the envelope list is empty")
    @pytest.mark.asyncio
    async def test_act_returns_empty_revealed_when_no_names(self):
        actor, _ = _make_actor()
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="*nods silently*"),
        )

        reply = await actor.act("look at him", {_LOC_KEY: "forum"})

        assert reply.revealed_names == ()
        assert reply.text == "*nods silently*"

    @allure.story("ActorReply return type")
    @allure.title("The Actor conversation history stores the narration string, not raw JSON")
    @pytest.mark.asyncio
    async def test_conversation_history_stores_narration(self):
        actor, _ = _make_actor()
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="I am Marcus.", revealed_names=["self"]),
        )
        await actor.act("who are you?", {_LOC_KEY: "forum"})
        assert actor._conversation[1].body == "I am Marcus."

    @allure.story("ActorReply return type")
    @allure.title("ActorEnvelope.revealed_names list is converted to a tuple in ActorReply")
    @pytest.mark.asyncio
    async def test_envelope_revealed_names_tuple_conversion(self):
        actor, _ = _make_actor()
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="I am Marcus, and that is Cassia.", revealed_names=["self", "Cassia"]),
        )

        reply = await actor.act("who are you?", {_LOC_KEY: "forum"})

        assert reply.revealed_names == ("self", "Cassia")

    @allure.story("ActorReply return type")
    @allure.title("ActorEnvelope with an empty revealed_names list maps to an empty tuple in ActorReply")
    @pytest.mark.asyncio
    async def test_empty_revealed_names_default(self):
        actor, _ = _make_actor()
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="Just a nod."),
        )

        reply = await actor.act("look at him", {_LOC_KEY: "forum"})

        assert reply.revealed_names == ()


@allure.epic("NPC Interaction")
@allure.feature("Revealed names envelope field")
class TestActorPromptDescribesEnvelope:
    """The Actor system prompt must describe the revealed_names envelope field."""

    @allure.story("Prompt instruction")
    @allure.title("The Actor system prompt instructs NPCs to populate revealed_names when uttering their own name")
    def test_prompt_describes_revealed_names_field(self):
        rendered = ACTOR_SYSTEM.render(
            npc_name="Marcus",
            npc_occupation="legionary",
            location_name="forum",
            npc_biography="A veteran.",
            personality_traits="stoic",
            speech_style="terse",
            npc_appearance="scarred",
            npc_inventory="gladius",
            accessible_knowledge="nothing notable",
            current_mood="neutral",
            physical_status="healthy",
            language="English",
            output_mode_dialogue="1",
        )
        assert "revealed_names" in rendered
        assert "self" in rendered


@allure.epic("NPC Interaction")
@allure.feature("Legacy rollback path")
class TestActorActLegacyModeIntegration:
    """``envelope_mode=False`` routes the Actor through the legacy parser.

    The rollback lever (``ACTOR_ENVELOPE_MODE=false`` in prod) is
    load-bearing — if the legacy adapter at ``cast.actor._act_legacy``
    silently bit-rots after a future field rename, the operator's only
    way to recover from an envelope outage becomes a no-op. These tests
    pin the end-to-end mapping.
    """

    @allure.story("Legacy path dispatch")
    @allure.title("envelope_mode=False drives _send (not _send_json) and parses trailing MOOD/STATUS/REVEALED tags")
    @pytest.mark.asyncio
    async def test_legacy_mode_parses_tags_end_to_end(self):
        actor, npc = _make_actor(envelope_mode=False)
        actor._send = AsyncMock(  # type: ignore[method-assign]
            return_value="*winces*\n[STATUS: wounded left arm]\n[REVEALED: self, Cassia]\n[MOOD: hostile]",
        )

        reply = await actor.act("who are you?", {_LOC_KEY: "forum"})

        assert reply.text == "*winces*"
        assert reply.revealed_names == ("self", "Cassia")
        assert npc.physical_status == "wounded left arm"
        assert npc.current_mood == "hostile"

    @allure.story("Legacy path dispatch")
    @allure.title("envelope_mode=False stores only the tag-stripped narration in conversation history")
    @pytest.mark.asyncio
    async def test_legacy_mode_conversation_history_is_clean(self):
        actor, _ = _make_actor(envelope_mode=False)
        actor._send = AsyncMock(  # type: ignore[method-assign]
            return_value="Hail.\n[MOOD: calm]",
        )

        await actor.act("greet him", {_LOC_KEY: "forum"})

        assert "[MOOD:" not in actor._conversation[1].body
        assert actor._conversation[1].body.strip() == "Hail."


@allure.epic("NPC Interaction")
@allure.feature("LLM integration boundary")
class TestActorEnvelopeIntegrationWithLLMClient:
    """Drive ``Actor.act`` through the real ``_send_json`` path.

    The envelope tests above stub ``_send_json`` itself, so the
    json-decode + pydantic-validate chain in ``base_performer_class`` is
    never exercised. These tests mock one layer lower —
    ``llm_client.send_message`` — so the integration is real and the
    fallback safety net at ``cast.actor._produce_envelope`` is actually
    covered.
    """

    @allure.story("Envelope-failure fallback")
    @allure.title("Three consecutive bad JSON responses yield a placeholder ActorReply instead of a 500")
    @pytest.mark.asyncio
    async def test_exhausted_retries_fall_back_to_placeholder(self):
        actor, _ = _make_actor(envelope_mode=True)
        actor.llm_client.send_message = AsyncMock(  # type: ignore[method-assign]
            return_value=_llm_body("still not json"),
        )

        reply = await actor.act("who are you?", {_LOC_KEY: "forum"})

        assert isinstance(reply, ActorReply)
        # Raw preview (from LLMJSONError.raw_response) is salvaged into the narration.
        assert "still not json" in reply.text
        assert reply.revealed_names == ()

    @allure.story("Envelope-failure fallback")
    @allure.title("Empty-body LLM responses after exhaustion fall back to the '...' placeholder narration")
    @pytest.mark.asyncio
    async def test_empty_response_falls_back_to_placeholder(self):
        actor, _ = _make_actor(envelope_mode=True)
        actor.llm_client.send_message = AsyncMock(  # type: ignore[method-assign]
            return_value=_llm_body(""),
        )

        reply = await actor.act("who are you?", {_LOC_KEY: "forum"})

        assert reply.text == "..."
