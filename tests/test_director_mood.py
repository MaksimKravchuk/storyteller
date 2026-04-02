"""Tests for Actor mood update integration via Director."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from cast.actor import Actor
from knowledge.graph import KnowledgeGraph
from knowledge.query import KnowledgeQueryEngine
from models.npc_card import NPCCard

_HOSTILE = "hostile"
_NEUTRAL = "neutral"


class TestActorMoodUpdate:
    @pytest.mark.asyncio
    async def test_mood_updated_after_response(self):
        actor, npc = _make_actor_with_npc(
            personality_traits=["aggressive"],
            speech_style="curt, military",
        )
        assert npc.current_mood == _NEUTRAL
        actor._send = AsyncMock(return_value=f"*tackles you*\n[MOOD: {_HOSTILE}]")
        actor_response = await actor.act("attack guard", {"location_name": "forum"})
        assert npc.current_mood == _HOSTILE
        assert "[MOOD:" not in actor_response

    @pytest.mark.asyncio
    async def test_mood_unchanged_when_no_tag(self):
        actor, npc = _make_actor_with_npc(
            npc_name="Merchant",
            occupation="merchant",
            personality_traits=["friendly"],
            speech_style="cheerful",
        )
        actor._send = AsyncMock(return_value="Welcome, friend!")
        await actor.act("hello", {"location_name": "market"})
        assert npc.current_mood == _NEUTRAL

    @pytest.mark.asyncio
    async def test_conversation_history_excludes_mood_tag(self):
        npc = NPCCard(name="Guard", occupation="guard")
        kq = KnowledgeQueryEngine(KnowledgeGraph())
        actor = Actor(llm_client=AsyncMock(), npc=npc, knowledge_query=kq)
        actor._send = AsyncMock(return_value=f"*blocks*\n[MOOD: {_HOSTILE}]")
        await actor.act("punch guard", {"location_name": "gate"})
        assert len(actor._conversation) == 2
        assert "[MOOD:" not in actor._conversation[1].content


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
