"""Tests for the turn-intent plumbing from Director routing plan to Narrator (KER-19).

Every ``ActionPlan`` variant carries a required ``intent`` field — a faithful
restatement of the player's stated goal. :class:`PlanExecutor` threads it
onto :attr:`TurnOutputs.intent` so the Narrator can honor it in prose,
even when the raw material drifts from the goal.
"""

from __future__ import annotations

import allure
import pytest

from cast.director_tools import ACTION_TOOLS
from cast.schemas.action_plan import TalkPlan
from cast.schemas.turn_outputs import TurnOutputs
from prompts.director_prompts import DIRECTOR_ACTION_ROUTING
from tests.director_helpers import make_director, make_game_state

_INTENT = "return to the Forum and speak to the guard"


@allure.epic("Game Timeline")
@allure.feature("Action routing")
class TestRoutingPlanIntent:
    @allure.story("Turn intent")
    @allure.title("Director routing prompt instructs the LLM to restate player intent")
    def test_routing_prompt_mentions_intent(self):
        rendered = DIRECTOR_ACTION_ROUTING.format(player_action="go back to the forum")
        assert "intent" in rendered.lower()
        assert "faithful" in rendered.lower()

    @allure.story("Turn intent")
    @allure.title("Every action-verb tool schema requires an intent argument")
    def test_every_action_tool_requires_intent(self):
        # `clarify` is a meta tool, not an action verb — skip it.
        verb_tools = [tool for tool in ACTION_TOOLS if tool.name != "clarify"]
        for tool in verb_tools:
            required = tool.parameters_schema.get("required", [])
            assert "intent" in required, "{0} must require 'intent'".format(tool.name)

    @allure.story("Turn intent")
    @allure.title("PlanExecutor propagates ActionPlan intent onto TurnOutputs before narration")
    @pytest.mark.asyncio
    async def test_plan_intent_flows_into_turn_outputs(self):
        gs = make_game_state()
        director = make_director(
            game_state=gs,
            route_response=TalkPlan(intent=_INTENT, targets=[], delegate_to=["narrator"]),
        )

        await director.act("go back to the forum and speak to the guard")

        narrator_call = director._executor._narrator.execute.call_args
        raw_outputs: TurnOutputs = narrator_call.kwargs["input_data"]
        assert raw_outputs.intent == _INTENT
