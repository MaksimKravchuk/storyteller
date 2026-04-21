"""Tests for the Actor revealed-names envelope field.

Covers two layers:

* ``Actor.act`` end-to-end — verifies the returned :class:`ActorReply`
  carries the revealed tokens from the JSON envelope and the spoken text
  is the ``narration`` field.
* The Actor system prompt — ensures it describes the ``revealed_names``
  JSON envelope field.

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
from models.npc_card import NPCCard
from prompts.actor_prompts import ACTOR_SYSTEM

_LOC_KEY = "location_name"


def _make_actor() -> tuple[Actor, NPCCard]:
    npc = NPCCard(name="Marcus", occupation="legionary")
    actor = Actor(
        llm_client=AsyncMock(),
        npc=npc,
        knowledge_query=KnowledgeQueryEngine(KnowledgeGraph()),
        envelope_mode=True,
    )
    return actor, npc


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
        )
        assert "revealed_names" in rendered
        assert "self" in rendered
