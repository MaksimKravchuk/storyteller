"""Tests for Actor mood and physical status update integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.actor import Actor
from cast.schemas.actor_reply import ActorEnvelope
from knowledge.graph import KnowledgeGraph
from knowledge.query import KnowledgeQueryEngine
from models.npc_card import NPCCard

_HOSTILE = "hostile"
_NEUTRAL = "neutral"
_GATE = "gate"
_LOC_KEY = "location_name"


@allure.epic("NPC Interaction")
@allure.feature("Mood & status tracking")
class TestActorMoodUpdate:
    @allure.story("Mood extraction")
    @allure.title("An actor envelope with mood=hostile updates the NPC's current_mood to hostile")
    @pytest.mark.asyncio
    async def test_mood_updated_after_response(self):
        actor, npc = _make_actor_with_npc(
            personality_traits=["aggressive"],
            speech_style="curt, military",
        )
        assert npc.current_mood == _NEUTRAL
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="*tackles you*", mood=_HOSTILE),
        )
        actor_response = await actor.act("attack guard", {_LOC_KEY: "forum"})
        assert npc.current_mood == _HOSTILE
        assert actor_response.text == "*tackles you*"

    @allure.story("Mood extraction")
    @allure.title("An actor envelope with mood=None leaves the NPC's current_mood untouched")
    @pytest.mark.asyncio
    async def test_mood_unchanged_when_no_tag(self):
        actor, npc = _make_actor_with_npc(
            npc_name="Merchant",
            occupation="merchant",
            personality_traits=["friendly"],
            speech_style="cheerful",
        )
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="Welcome, friend!"),
        )
        await actor.act("hello", {_LOC_KEY: "market"})
        assert npc.current_mood == _NEUTRAL

    @allure.story("Mood extraction")
    @allure.title("The conversation history stores the narration string, not raw JSON")
    @pytest.mark.asyncio
    async def test_conversation_history_excludes_mood_tag(self):
        npc = NPCCard(name="Guard", occupation="guard")
        kq = KnowledgeQueryEngine(KnowledgeGraph())
        actor = Actor(llm_client=AsyncMock(), npc=npc, knowledge_query=kq)
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="*blocks*", mood=_HOSTILE),
        )
        await actor.act("punch guard", {_LOC_KEY: _GATE})
        assert len(actor._conversation) == 2
        assert actor._conversation[1].body == "*blocks*"


@allure.epic("NPC Interaction")
@allure.feature("Mood & status tracking")
class TestActorStatusUpdate:
    @allure.story("Status updates")
    @allure.title("An actor envelope with status set writes the new physical_status onto the NPC card")
    @pytest.mark.asyncio
    async def test_status_updated_after_response(self):
        actor, npc = _make_actor_with_npc()
        assert npc.physical_status == "healthy"
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="*clutches arm*", status="wounded left arm"),
        )
        response = await actor.act("slash guard's arm", {_LOC_KEY: _GATE})
        assert npc.physical_status == "wounded left arm"
        assert response.text == "*clutches arm*"

    @allure.story("Status updates")
    @allure.title("An actor envelope with status=None leaves the NPC's physical_status as healthy")
    @pytest.mark.asyncio
    async def test_status_unchanged_when_no_tag(self):
        actor, npc = _make_actor_with_npc()
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="*blocks the attack*"),
        )
        await actor.act("attack guard", {_LOC_KEY: _GATE})
        assert npc.physical_status == "healthy"

    @allure.story("Status updates")
    @allure.title("An envelope with both mood and status fields updates the NPC card for both")
    @pytest.mark.asyncio
    async def test_both_mood_and_status_extracted(self):
        actor, npc = _make_actor_with_npc()
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="*falls to knees*", mood=_HOSTILE, status="barely standing"),
        )
        response = await actor.act("hit guard hard", {_LOC_KEY: _GATE})
        assert npc.current_mood == _HOSTILE
        assert npc.physical_status == "barely standing"
        assert response.text == "*falls to knees*"

    @allure.story("Status updates")
    @allure.title("The conversation history stores the narration, not raw JSON")
    @pytest.mark.asyncio
    async def test_conversation_history_excludes_status_tag(self):
        actor, npc = _make_actor_with_npc()
        actor._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ActorEnvelope(narration="*winces*", status="wounded"),
        )
        await actor.act("punch guard", {_LOC_KEY: _GATE})
        assert actor._conversation[1].body == "*winces*"


def _make_actor_with_npc(
    npc_name="Guard",
    occupation="city guard",
    **npc_kwargs,
):
    """Create a mocked Actor + NPCCard pair."""
    npc = NPCCard(name=npc_name, occupation=occupation, **npc_kwargs)
    actor = Actor(
        llm_client=AsyncMock(),
        npc=npc,
        knowledge_query=KnowledgeQueryEngine(KnowledgeGraph()),
    )
    return actor, npc
