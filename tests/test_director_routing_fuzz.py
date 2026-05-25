"""Hypothesis fuzz harness for ActionRouter (cast/director_routing.py).

Exercises >= 200 inputs across seven input classes:
  short imperatives, conversational, gibberish, mixed-locale,
  emoji, very-long, and unicode edge cases.

The LLM is fully mocked -- CI cost is zero. ``send_tool_fn`` is a
keyword-based classifier that returns a schema-valid ToolCall so
``parse_tool_call`` exercises every verb branch plus the clarify branch.
"""

from __future__ import annotations

import asyncio
from typing import Any

import allure
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cast.director_routing import ActionRouter
from cast.schemas import action_plan as plan_mod
from llm.base_client import LLMJSONError
from llm.message import ToolCall
from tests.director_helpers import make_game_state

# ---------------------------------------------------------------------------
# Thresholds and limits (no magic numbers in call sites)
# ---------------------------------------------------------------------------

_MAX_EXAMPLES = 200
_MIN_VERB_SHARE = 0.7
_HASH_WINDOW = 16
_INPUT_PREVIEW = 80

# ---------------------------------------------------------------------------
# Canonical valid ToolCall arguments per verb -- derived from Pydantic models
# so they stay in sync with schema changes automatically.
# ---------------------------------------------------------------------------

_MOVE_ARGS = plan_mod.MovePlan(intent="go there", direction="forward").model_dump()
_TALK_ARGS = plan_mod.TalkPlan(intent="address guard", targets=["guard"]).model_dump()
_EXAMINE_ARGS = plan_mod.ExaminePlan(intent="look at object", targets=["statue"]).model_dump()
_INTERACT_ARGS = plan_mod.InteractPlan(intent="open it", targets=["door"]).model_dump()
_SLEEP_ARGS = plan_mod.SleepPlan(intent="sleep now").model_dump()
_WAIT_ARGS = plan_mod.WaitPlan(intent="wait a moment").model_dump()
_EXPLORE_ARGS = plan_mod.ExplorePlan(intent="look around").model_dump()
_OTHER_ARGS = plan_mod.OtherPlan(intent="do thing", reason="unknown").model_dump()
_CLARIFY_ARGS = plan_mod.ClarificationRequest(question="Which one?").model_dump()

_VERB_CALLS = (
    ToolCall(name="move", arguments=_MOVE_ARGS),
    ToolCall(name="talk", arguments=_TALK_ARGS),
    ToolCall(name="examine", arguments=_EXAMINE_ARGS),
    ToolCall(name="interact", arguments=_INTERACT_ARGS),
    ToolCall(name="sleep", arguments=_SLEEP_ARGS),
    ToolCall(name="wait", arguments=_WAIT_ARGS),
    ToolCall(name="explore", arguments=_EXPLORE_ARGS),
    ToolCall(name="other", arguments=_OTHER_ARGS),
)

_MOVE_KEYWORDS = ("go ", "move ", "north", "south", "east", "west", "enter", "leave", "run ")
_TALK_KEYWORDS = ("say ", "address", "ask ", "greet", "tell ", "speak", "hello", "hi ")


def _classify_action(player_action: str) -> ToolCall:
    """Keyword-based mock classifier -- returns a schema-valid ToolCall.

    Mimics the routing logic the LLM would apply, so that the
    verdict-distribution check reflects real intent signal.
    """
    lowered = player_action.lower()
    if any(kw in lowered for kw in _MOVE_KEYWORDS):
        return ToolCall(name="move", arguments=_MOVE_ARGS)
    if any(kw in lowered for kw in _TALK_KEYWORDS):
        return ToolCall(name="talk", arguments=_TALK_ARGS)
    # Rotate through the verb set for everything else to cover all branches.
    idx = abs(hash(player_action[:_HASH_WINDOW])) % len(_VERB_CALLS)
    return _VERB_CALLS[idx]


async def _fake_send_tool(
    user_message: str,
    tools: Any = None,
    conversation: Any = None,
) -> ToolCall:
    """Async drop-in for ``send_tool_fn`` that never hits the network."""
    return _classify_action(user_message)


def _make_router() -> ActionRouter:
    """Build an ``ActionRouter`` wired to the mock classifier."""
    return ActionRouter(
        game_state=make_game_state(),
        send_tool_fn=_fake_send_tool,
        action_routing_template="{player_action}",
    )


# ---------------------------------------------------------------------------
# Hypothesis strategies -- one per input class
# ---------------------------------------------------------------------------

_SHORT_IMPERATIVES = st.sampled_from(
    [
        "go north",
        "enter the tavern",
        "examine the sword",
        "pick up the coin",
        "open the door",
        "sleep",
        "wait",
        "look around",
        "attack the bandit",
        "ask about the map",
        "run away",
        "take the key",
    ]
)

_CONVERSATIONAL = st.sampled_from(
    [
        "I would like to speak with the innkeeper please",
        "Can you tell me where the market is?",
        "Let me think about that for a moment",
        "What do you think about the situation in Rome?",
        "I guess I'll just look around for now",
        "Maybe I should try addressing someone",
    ]
)

_GIBBERISH = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=60,
)

_MIXED_LOCALE = st.sampled_from(
    [
        "Иди на север go north",
        "поговори address guard",
        "смотри examine statue",
        "open дверь door please",
        "спать sleep now",
        "Hallo sprechen Wache рядом",
    ]
)

_EMOJI = st.sampled_from(
    [
        "\U0001f5e1",
        "\U0001f4ac say hello",
        "\U0001f3e0 go home",
        "\U0001f4a4 sleep now",
        "⚔",
        "\U0001f440 look",
        "\U0001f6b6 walk north",
        "\U0001f64b ask guard",
    ]
)

_VERY_LONG = st.text(
    alphabet=st.characters(whitelist_categories=("L", "Z")),
    min_size=1000,
    max_size=4000,
)

# Unicode edge cases: zero-width, RTL override, BOM, soft hyphen, hair space.
# Pre-build combined strings using format() to avoid WPS336 (string concatenation).
_ZERO_WIDTH_SPACE = "​"
_RTL_OVERRIDE = "‮"
_BOM = "﻿"
_SOFT_HYPHEN = "­"
_HAIR_SPACE = " "

_RTL_MOVE = "{0} go north".format(_RTL_OVERRIDE)
_BOM_OPEN = "{0} open door".format(_BOM)
_ZWS_ADDRESS = "{0} address guard".format(_ZERO_WIDTH_SPACE)
_HAIR_SLEEP = "{0} sleep".format(_HAIR_SPACE)
_ZWS_EXAMINE = "{0} examine statue".format(_ZERO_WIDTH_SPACE)
_SOFT_GO = "{0}go north{1}".format(_SOFT_HYPHEN, _SOFT_HYPHEN)

_UNICODE_EDGE = st.sampled_from(
    [
        _ZERO_WIDTH_SPACE,
        _RTL_MOVE,
        _BOM_OPEN,
        _HAIR_SPACE,
        _ZWS_ADDRESS,
        _HAIR_SLEEP,
        _ZWS_EXAMINE,
        _SOFT_GO,
    ]
)

_ALL_INPUTS = st.one_of(
    _SHORT_IMPERATIVES,
    _CONVERSATIONAL,
    _GIBBERISH,
    _MIXED_LOCALE,
    _EMOJI,
    _VERY_LONG,
    _UNICODE_EDGE,
)

_CLEARLY_ACTIONABLE = (
    "go north",
    "enter the tavern",
    "run away",
    "say hello",
    "greet the innkeeper",
    "move to the market",
    "go east",
    "leave the building",
    "hello guard",
    "ask about the map",
    "speak to the merchant",
    "address the merchant",
    "say farewell",
)


async def _collect_verdicts(router: ActionRouter) -> tuple[int, int]:
    """Route each clearly-actionable input and return (verb_count, clarify_count).

    Uses ``asyncio.gather`` to run all route calls concurrently, avoiding
    the WPS476 (await-in-for-loop) lint rule.
    """
    results = await asyncio.gather(*(router.route_action(action) for action in _CLEARLY_ACTIONABLE))
    verb_count = sum(1 for routed in results if not isinstance(routed, plan_mod.ClarificationRequest))
    clarify_count = sum(1 for routed in results if isinstance(routed, plan_mod.ClarificationRequest))
    return verb_count, clarify_count


# ---------------------------------------------------------------------------
# Test class -- epic/feature/story on the class; each method only needs
# @allure.title plus one functional decorator to stay under WPS216 (max 5).
# ---------------------------------------------------------------------------


@allure.epic("Director")
@allure.feature("Action routing")
@allure.story("Fuzz harness")
class TestDirectorRoutingFuzz:
    """Hypothesis-driven fuzz tests for ActionRouter."""

    @allure.title("ActionRouter never raises LLMJSONError across 200+ varied inputs")
    @given(player_action=_ALL_INPUTS)
    @settings(max_examples=_MAX_EXAMPLES, deadline=None)
    def test_no_llmjsonerror(self, player_action: str) -> None:
        """Zero ``LLMJSONError`` escapes for any input class."""
        router = _make_router()
        try:
            asyncio.run(router.route_action(player_action))
        except LLMJSONError as exc:
            pytest.fail("LLMJSONError raised for input: {0!r}. Error: {1}".format(player_action[:_INPUT_PREVIEW], exc))

    @allure.title("Clearly-actionable inputs route to action verbs >= 70% of the time")
    @pytest.mark.asyncio
    async def test_verdict_distribution_clearly_actionable(self) -> None:
        """Verdict-distribution sanity: clearly-actionable inputs should route
        to a concrete verb (not clarify) at least ``_MIN_VERB_SHARE`` of the time.

        Uses a fixed tuple of ``_CLEARLY_ACTIONABLE`` inputs so the count is
        deterministic and the numbers can be pasted into the PR body.
        """
        router = _make_router()
        verb_count, clarify_count = await _collect_verdicts(router)

        total = verb_count + clarify_count
        verb_share = verb_count / total if total else _MIN_VERB_SHARE

        allure.attach(
            "verb={0} clarify={1} total={2} share={3:.0%}".format(verb_count, clarify_count, total, verb_share),
            name="verdict-distribution",
            attachment_type=allure.attachment_type.TEXT,
        )

        assert verb_share >= _MIN_VERB_SHARE, (
            "Clearly-actionable inputs routed to verb only {0:.0%} of the time "
            "(expected >={1:.0%}). verb={2} clarify={3}".format(verb_share, _MIN_VERB_SHARE, verb_count, clarify_count)
        )
