"""Tests for Actor mood and physical status update integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.actor import Actor
from cast.actor_tags import extract_mood as _actor_extract_mood, extract_status as _extract_status
from knowledge.graph import KnowledgeGraph
from knowledge.query import KnowledgeQueryEngine
from models.npc_card import NPCCard

_HOSTILE = "hostile"
_NEUTRAL = "neutral"
_GATE = "gate"
_STATUS_TAG = "[STATUS:"
_LOC_KEY = "location_name"


@allure.epic("NPC Interaction")
@allure.feature("Mood & status tracking")
class TestActorMoodUpdate:
    @allure.story("Mood extraction")
    @allure.title("An actor response with a [MOOD: hostile] tag updates the NPC's current_mood to hostile")
    @pytest.mark.asyncio
    async def test_mood_updated_after_response(self):
        actor, npc = _make_actor_with_npc(
            personality_traits=["aggressive"],
            speech_style="curt, military",
        )
        assert npc.current_mood == _NEUTRAL
        actor._send = AsyncMock(return_value=f"*tackles you*\n[MOOD: {_HOSTILE}]")
        actor_response = await actor.act("attack guard", {_LOC_KEY: "forum"})
        assert npc.current_mood == _HOSTILE
        assert "[MOOD:" not in actor_response.text

    @allure.story("Mood extraction")
    @allure.title("An actor response without a [MOOD:] tag leaves the NPC's current_mood untouched")
    @pytest.mark.asyncio
    async def test_mood_unchanged_when_no_tag(self):
        actor, npc = _make_actor_with_npc(
            npc_name="Merchant",
            occupation="merchant",
            personality_traits=["friendly"],
            speech_style="cheerful",
        )
        actor._send = AsyncMock(return_value="Welcome, friend!")
        await actor.act("hello", {_LOC_KEY: "market"})
        assert npc.current_mood == _NEUTRAL

    @allure.story("Mood extraction")
    @allure.title("The [MOOD:] tag is stripped from the stored actor conversation history")
    @pytest.mark.asyncio
    async def test_conversation_history_excludes_mood_tag(self):
        npc = NPCCard(name="Guard", occupation="guard")
        kq = KnowledgeQueryEngine(KnowledgeGraph())
        actor = Actor(llm_client=AsyncMock(), npc=npc, knowledge_query=kq)
        actor._send = AsyncMock(return_value=f"*blocks*\n[MOOD: {_HOSTILE}]")
        await actor.act("punch guard", {_LOC_KEY: _GATE})
        assert len(actor._conversation) == 2
        assert "[MOOD:" not in actor._conversation[1].body


@allure.epic("NPC Interaction")
@allure.feature("Mood & status tracking")
class TestExtractMood:
    @allure.story("Mood tag extraction")
    @allure.title("Actor mood extraction leaves text unchanged and returns no mood when there is no [MOOD:] tag")
    def test_no_mood_tag(self):
        text, mood = _actor_extract_mood("*draws his sword* — Stand back!")
        assert text == "*draws his sword* — Stand back!"
        assert mood is None

    @allure.story("Mood tag extraction")
    @allure.title("Actor mood extraction strips a trailing [MOOD: hostile] tag and returns the mood value")
    def test_mood_tag_at_end(self):
        text, mood = _actor_extract_mood(f"*lunges at you with a spear*\n[MOOD: {_HOSTILE}]")
        assert text == "*lunges at you with a spear*"
        assert mood == _HOSTILE

    @allure.story("Mood tag extraction")
    @allure.title("Actor mood extraction normalizes uppercase mood values to lowercase")
    def test_mood_tag_uppercase_normalised(self):
        text, mood = _actor_extract_mood("Back off!\n[MOOD: ENRAGED]")
        assert mood == "enraged"

    @allure.story("Mood tag extraction")
    @allure.title("Actor mood extraction tolerates extra whitespace between the [MOOD:] label and the value")
    def test_mood_tag_with_extra_space_before_word(self):
        text, mood = _actor_extract_mood("Help!\n[MOOD:  terrified]")
        assert mood == "terrified"

    @allure.story("Mood tag extraction")
    @allure.title("A [MOOD:] tag that is not at the end of the response is ignored and left in the text")
    def test_mood_tag_not_at_end_is_ignored(self):
        text, mood = _actor_extract_mood(f"[MOOD: {_HOSTILE}]\nI will destroy you!")
        assert mood is None
        assert f"[MOOD: {_HOSTILE}]" in text

    @allure.story("Mood tag extraction")
    @allure.title("Actor mood extraction handles an empty response string without error")
    def test_empty_string(self):
        text, mood = _actor_extract_mood("")
        assert text == ""
        assert mood is None


@allure.epic("NPC Interaction")
@allure.feature("Mood & status tracking")
class TestExtractStatus:
    @allure.story("Status extraction")
    @allure.title("A single-word [STATUS: wounded] tag is extracted and removed from the response body")
    def test_extracts_single_word(self):
        text, status = _extract_status("*stumbles back*\n[STATUS: wounded]")
        assert status == "wounded"
        assert _STATUS_TAG not in text

    @allure.story("Status extraction")
    @allure.title("A multi-word [STATUS: wounded left arm] tag is captured in full and stripped from the text")
    def test_extracts_multi_word(self):
        text, status = _extract_status("*grabs arm*\n[STATUS: wounded left arm]")
        assert status == "wounded left arm"
        assert _STATUS_TAG not in text

    @allure.story("Status extraction")
    @allure.title("A response with no [STATUS:] tag returns None for the status and the text unchanged")
    def test_returns_none_when_no_tag(self):
        text, status = _extract_status("Hello there!")
        assert status is None
        assert text == "Hello there!"

    @allure.story("Status extraction")
    @allure.title("Leading and trailing whitespace inside a [STATUS:] tag is stripped before storing")
    def test_strips_whitespace(self):
        _, status = _extract_status("*falls*\n[STATUS:  barely standing  ]")
        assert status == "barely standing"


@allure.epic("NPC Interaction")
@allure.feature("Mood & status tracking")
class TestActorStatusUpdate:
    @allure.story("Status updates")
    @allure.title("An actor response with a [STATUS:] tag writes the new physical_status onto the NPC card")
    @pytest.mark.asyncio
    async def test_status_updated_after_response(self):
        actor, npc = _make_actor_with_npc()
        assert npc.physical_status == "healthy"
        actor._send = AsyncMock(return_value="*clutches arm*\n[STATUS: wounded left arm]")
        response = await actor.act("slash guard's arm", {_LOC_KEY: _GATE})
        assert npc.physical_status == "wounded left arm"
        assert _STATUS_TAG not in response.text

    @allure.story("Status updates")
    @allure.title("An actor response without a [STATUS:] tag leaves the NPC's physical_status as healthy")
    @pytest.mark.asyncio
    async def test_status_unchanged_when_no_tag(self):
        actor, npc = _make_actor_with_npc()
        actor._send = AsyncMock(return_value="*blocks the attack*")
        await actor.act("attack guard", {_LOC_KEY: _GATE})
        assert npc.physical_status == "healthy"

    @allure.story("Status updates")
    @allure.title("A response containing both [MOOD:] and [STATUS:] tags updates the NPC and strips both markers")
    @pytest.mark.asyncio
    async def test_both_mood_and_status_extracted(self):
        actor, npc = _make_actor_with_npc()
        actor._send = AsyncMock(
            return_value="*falls to knees*\n[MOOD: hostile]\n[STATUS: barely standing]",
        )
        response = await actor.act("hit guard hard", {_LOC_KEY: _GATE})
        assert npc.current_mood == _HOSTILE
        assert npc.physical_status == "barely standing"
        assert "[MOOD:" not in response.text
        assert _STATUS_TAG not in response.text

    @allure.story("Status updates")
    @allure.title("The [STATUS:] tag is removed from the stored actor conversation history")
    @pytest.mark.asyncio
    async def test_conversation_history_excludes_status_tag(self):
        actor, npc = _make_actor_with_npc()
        actor._send = AsyncMock(return_value="*winces*\n[STATUS: wounded]")
        await actor.act("punch guard", {_LOC_KEY: _GATE})
        assert _STATUS_TAG not in actor._conversation[1].body


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
