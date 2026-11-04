"""Real-model Actor smoke tests — dialogue mode and NPC-turn (action) mode.

The Actor has two distinct output shapes:

* **Dialogue mode** (default): returns an :class:`ActorReply` whose
  ``text`` is the spoken prose. The model is told the NPC's distinctive
  name and occupation; we assert the reply parses as a non-empty
  string. The input-tied guard is the NPC's stated profession surfacing
  in the dialogue (e.g. a blacksmith referring to forge, anvil, metal).
* **NPC-turn mode**: invoked when ``context["is_npc_turn"]`` is true.
  Returns an ``ActorReply`` whose ``text`` is raw action JSON shaped
  ``{"action", "type", "target"}``. We assert it parses as JSON with
  the expected keys and the ``type`` is one of the action-type enum
  values ``NPCTurnResolver`` accepts.
"""

from __future__ import annotations

import json

import allure
import pytest

from cast.actor import Actor
from cast.schemas.actor_reply import ActorReply
from knowledge.graph import KnowledgeGraph
from knowledge.query import KnowledgeQueryEngine
from models.npc_card import NPCCard
from tests.e2e._real_llm import real_llm_for

_BLACKSMITH = NPCCard(
    name="Aelius",
    occupation="blacksmith",
    biography="A veteran ironworker who served as a smith with the Tenth Legion before settling in town.",
    appearance="Broad shoulders, soot-streaked apron, a burn-scar across the forearm.",
    personality_traits=["gruff", "honest"],
    speech_style="terse, blunt sentences with the cadence of a soldier",
    inventory=["hammer", "tongs"],
    attributes={"strength": 9, "education": 2},
)
# Trade vocabulary a Roman-era blacksmith plausibly volunteers when
# asked about his work. Broad on purpose — the assertion catches a
# regression where the NPC persona is dropped from the prompt entirely
# (model would default to a generic stranger), not narrow stylistic
# choices about which word the model picks.
_BLACKSMITH_KEYWORDS = (
    "forge",
    "anvil",
    "hammer",
    "iron",
    "metal",
    "smith",
    "steel",
    "coal",
    "nail",
    "horseshoe",
    "hinge",
    "blade",
    "repair",
)
_GUARD = NPCCard(
    name="Severus",
    occupation="city guard",
    biography="A veteran patrolman who has walked the night shift for fifteen years.",
    appearance="Standard guard uniform, tired eyes.",
    personality_traits=["watchful", "tired"],
    speech_style="curt, official",
    inventory=["short sword", "lantern"],
)
_NPC_TURN_PROMPT = (
    "Decide what you do this turn while a stranger is loitering near the city gate at night. "
    "Respond with the action JSON only."
)
# The enum the actor system prompt documents at
# ``prompts/actor_prompts.py:161``. Must be kept in sync if the prompt
# vocabulary changes — a prompt drift this test should catch is exactly
# the model emitting a new type the assertion would mark as a violation.
_ALLOWED_ACTION_TYPES = frozenset(("ATTACK", "TALK", "MOVE", "IDLE", "STEALTH", "PERSUADE", "DECEIVE", "INTIMIDATE"))


def _empty_query_engine() -> KnowledgeQueryEngine:
    """Build an Actor knowledge engine backed by an empty graph."""
    return KnowledgeQueryEngine(KnowledgeGraph())


pytestmark = pytest.mark.live


@allure.epic("AI Agent Orchestration")
@allure.feature("Actor real-model dialogue and NPC-turn modes")
class TestActorRealModel:
    @allure.story("Dialogue mode preserves NPC profession")
    @allure.title("A real Actor model speaks in voice for the NPC's distinctive profession")
    @pytest.mark.asyncio
    async def test_real_model_dialogue_reflects_profession(self):
        actor = Actor(
            llm_client=real_llm_for("actor"),
            npc=_BLACKSMITH.model_copy(),
            knowledge_query=_empty_query_engine(),
            language="English",
        )

        reply = await actor.act(
            "What kind of work brings you the most coin these days?",
            {"location_name": "Aelius's forge in the trade quarter"},
        )

        assert isinstance(reply, ActorReply)
        assert reply.text.strip(), "Actor returned empty dialogue"
        # Input-tied: a blacksmith answering a question about his work
        # should reference the trade in some way (forge/anvil/iron/etc).
        # Failure mode this catches: the NPC profile not interpolated
        # into the system prompt body, so the model invents a generic
        # persona.
        lower = reply.text.lower()
        assert any(keyword in lower for keyword in _BLACKSMITH_KEYWORDS), (
            "Blacksmith dialogue surfaced no trade-related vocabulary.\nReply was:\n{0}".format(reply.text)
        )

    @allure.story("NPC-turn mode emits action JSON")
    @allure.title("A real Actor in NPC-turn mode returns a structured action JSON payload")
    @pytest.mark.asyncio
    async def test_real_model_npc_turn_emits_action_json(self):
        actor = Actor(
            llm_client=real_llm_for("actor"),
            npc=_GUARD.model_copy(),
            knowledge_query=_empty_query_engine(),
            language="English",
        )

        reply = await actor.act(
            _NPC_TURN_PROMPT,
            {"location_name": "the city gate at night", "is_npc_turn": True},
        )

        assert isinstance(reply, ActorReply)
        assert reply.text.strip(), "Actor returned empty action JSON"
        # Input-tied: NPC-turn mode parses as JSON with the documented
        # keys. Failure mode this catches: the action system-prompt swap
        # not taking effect, so the model returns the dialogue envelope
        # shape instead.
        try:
            payload = json.loads(reply.text)
        except json.JSONDecodeError as exc:
            pytest.fail(f"NPC-turn actor returned non-JSON text: {reply.text!r} (decode error: {exc})")
        assert {"action", "type", "target"}.issubset(payload.keys()), (
            "Action JSON missing required keys; got: {0!r}".format(payload)
        )
        assert payload["type"] in _ALLOWED_ACTION_TYPES, "Action type {0!r} not in allowed enum {1}".format(
            payload["type"], sorted(_ALLOWED_ACTION_TYPES)
        )
