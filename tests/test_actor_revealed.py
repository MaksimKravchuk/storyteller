"""Tests for the Actor ``[REVEALED: ...]`` tag.

Covers three layers:

* :func:`cast.actor_tags.extract_revealed` — the regex-level extractor.
* :func:`cast.actor_tags.strip_trailing_tags` — the order-independent
  multi-tag stripper that ``Actor.act`` relies on when the LLM emits
  MOOD / STATUS / REVEALED tags in any permutation.
* ``Actor.act`` end-to-end — verifies the returned :class:`ActorReply`
  carries the revealed tokens and the spoken text has the tag stripped.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.actor import Actor
from cast.actor_tags import extract_revealed, strip_trailing_tags
from cast.schemas.actor_reply import ActorReply
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
    )
    return actor, npc


@allure.epic("NPC Interaction")
@allure.feature("Revealed tag extraction")
class TestExtractRevealed:
    @allure.story("Revealed tag regex")
    @allure.title("A single [REVEALED: self] token resolves to ``['self']`` and is stripped from the text")
    def test_single_self_token(self):
        text, tokens = extract_revealed("I am Marcus.\n[REVEALED: self]")
        assert tokens == ["self"]
        assert "[REVEALED:" not in text

    @allure.story("Revealed tag regex")
    @allure.title("A multi-token [REVEALED: self, Cassia] tag splits on commas and trims whitespace")
    def test_multiple_tokens(self):
        text, tokens = extract_revealed("I am Marcus, and that is Cassia.\n[REVEALED: self, Cassia]")
        assert tokens == ["self", "Cassia"]
        assert "[REVEALED:" not in text

    @allure.story("Revealed tag regex")
    @allure.title("Tokens with extra surrounding whitespace are stripped")
    def test_tokens_whitespace_trimmed(self):
        _, tokens = extract_revealed("Greetings.\n[REVEALED:   self ,   Cassia  ]")
        assert tokens == ["self", "Cassia"]

    @allure.story("Revealed tag regex")
    @allure.title("A response without any [REVEALED:] tag returns an empty list and unchanged text")
    def test_no_tag_returns_empty(self):
        text, tokens = extract_revealed("Just a line.")
        assert tokens == []
        assert text == "Just a line."

    @allure.story("Revealed tag regex")
    @allure.title("A malformed [REVEALED:] tag with an empty body yields an empty token list")
    def test_empty_body_returns_empty(self):
        text, tokens = extract_revealed("Hmm.\n[REVEALED: ]")
        assert tokens == []
        # The malformed tag is still stripped since the regex matches the
        # bracket structure; only the tokens are filtered to the empty list.
        assert "[REVEALED:" not in text

    @allure.story("Revealed tag regex")
    @allure.title("A [REVEALED:] tag not anchored at end-of-string is ignored")
    def test_tag_not_at_end_is_ignored(self):
        raw = "[REVEALED: self]\nContinuing conversation."
        text, tokens = extract_revealed(raw)
        assert tokens == []
        assert text == raw


@allure.epic("NPC Interaction")
@allure.feature("Revealed tag extraction")
class TestStripTrailingTagsOrderIndependence:
    """The LLM can emit MOOD / STATUS / REVEALED in any sequence.

    The single-pass anchored extractors only strip the outermost tag;
    the loop in :func:`strip_trailing_tags` guarantees every trailing
    tag is captured regardless of ordering.
    """

    @allure.story("Multi-tag permutation")
    @allure.title("STATUS then REVEALED then MOOD — all three tags are captured and text is clean")
    def test_status_revealed_mood_permutation(self):
        bag = strip_trailing_tags("*winces*\n[STATUS: wounded]\n[REVEALED: self]\n[MOOD: wary]")
        assert bag.mood == "wary"
        assert bag.status == "wounded"
        assert bag.revealed == ["self"]
        assert "[STATUS:" not in bag.text
        assert "[MOOD:" not in bag.text
        assert "[REVEALED:" not in bag.text
        assert bag.text.strip() == "*winces*"

    @allure.story("Multi-tag permutation")
    @allure.title("MOOD then STATUS then REVEALED — extraction still captures all three")
    def test_mood_status_revealed_permutation(self):
        bag = strip_trailing_tags("Hail.\n[MOOD: friendly]\n[STATUS: healthy]\n[REVEALED: self, Cassia]")
        assert bag.mood == "friendly"
        assert bag.status == "healthy"
        assert bag.revealed == ["self", "Cassia"]

    @allure.story("Multi-tag permutation")
    @allure.title("Only one tag trailing — the loop captures it and leaves the others as None")
    def test_only_one_tag(self):
        bag = strip_trailing_tags("I am Marcus.\n[REVEALED: self]")
        assert bag.mood is None
        assert bag.status is None
        assert bag.revealed == ["self"]

    @allure.story("Multi-tag permutation")
    @allure.title("No trailing tags returns (text, None, None, [])")
    def test_no_tags(self):
        bag = strip_trailing_tags("Just a sentence.")
        assert bag.text == "Just a sentence."
        assert bag.mood is None
        assert bag.status is None
        assert bag.revealed == []

    @allure.story("Multi-tag permutation")
    @allure.title("Duplicate [MOOD:] tags collapse to the first/outermost value and both are stripped from text")
    def test_duplicate_mood_first_wins(self):
        bag = strip_trailing_tags("Back off!\n[MOOD: angry]\n[MOOD: calm]")
        assert bag.mood == "calm"
        assert "[MOOD:" not in bag.text
        assert bag.text.strip() == "Back off!"


@allure.epic("NPC Interaction")
@allure.feature("Revealed tag extraction")
class TestActorActReturnsActorReply:
    @allure.story("ActorReply return type")
    @allure.title("Actor.act returns an ActorReply whose revealed_names carries the tag tokens")
    @pytest.mark.asyncio
    async def test_act_returns_actor_reply_with_tokens(self):
        actor, _ = _make_actor()
        actor._send = AsyncMock(return_value="I am Marcus.\n[REVEALED: self]")

        reply = await actor.act("who are you?", {_LOC_KEY: "forum"})

        assert isinstance(reply, ActorReply)
        assert reply.revealed_names == ("self",)
        assert "[REVEALED:" not in reply.text
        assert reply.text.strip() == "I am Marcus."

    @allure.story("ActorReply return type")
    @allure.title("Actor.act returns an ActorReply with an empty revealed_names when no tag is emitted")
    @pytest.mark.asyncio
    async def test_act_returns_empty_revealed_when_tag_absent(self):
        actor, _ = _make_actor()
        actor._send = AsyncMock(return_value="*nods silently*")

        reply = await actor.act("look at him", {_LOC_KEY: "forum"})

        assert reply.revealed_names == ()
        assert reply.text == "*nods silently*"

    @allure.story("ActorReply return type")
    @allure.title("The Actor conversation history stores the tag-stripped line, not the raw tagged output")
    @pytest.mark.asyncio
    async def test_conversation_history_stores_cleaned_text(self):
        actor, _ = _make_actor()
        actor._send = AsyncMock(return_value="I am Marcus.\n[REVEALED: self]")
        await actor.act("who are you?", {_LOC_KEY: "forum"})
        assert "[REVEALED:" not in actor._conversation[1].body


@allure.epic("NPC Interaction")
@allure.feature("Revealed tag extraction")
class TestActorPromptInstructsRevealedTag:
    """The Actor system prompt must teach the LLM how to emit the tag."""

    @allure.story("Prompt instruction")
    @allure.title("The Actor system prompt instructs NPCs to append [REVEALED: self] when uttering their own name")
    def test_prompt_mentions_revealed_self(self):
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
        assert "[REVEALED:" in rendered
        assert "self" in rendered
