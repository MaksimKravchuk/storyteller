"""Tests for the turn-intent plumbing from Director routing plan to Narrator (KER-19).

The Director's routing plan now carries an ``intent`` field — a faithful
restatement of the player's stated goal. :class:`PlanExecutor` threads it
onto :attr:`TurnOutputs.intent` so the Narrator can honor it in prose,
even when the raw material drifts from the goal.
"""

from __future__ import annotations

import allure
import pytest

from cast.schemas.turn_outputs import TurnOutputs
from prompts.director_prompts import DIRECTOR_ACTION_ROUTING
from tests.director_helpers import make_director, make_game_state

_INTENT = "return to the Forum and speak to the guard"


def _route_with_intent(action_type: str, intent: str) -> dict:
    """Build a route_response dict that includes a stated intent."""
    return {
        "action_type": action_type,
        "targets": [],
        "needs_clarification": False,
        "delegate_to": ["narrator"],
        "intent": intent,
    }


@allure.epic("Game Timeline")
@allure.feature("Action routing")
class TestRoutingPlanIntent:
    @allure.story("Turn intent")
    @allure.title("Director routing prompt instructs the LLM to emit an intent field in every plan")
    def test_routing_prompt_includes_intent_field(self):
        rendered = DIRECTOR_ACTION_ROUTING.render(player_action="go back to the forum")
        assert '"intent"' in rendered
        assert "faithful restatement" in rendered

    @allure.story("Turn intent")
    @allure.title("PlanExecutor propagates routing plan intent onto TurnOutputs before narration")
    @pytest.mark.asyncio
    async def test_plan_intent_flows_into_turn_outputs(self):
        gs = make_game_state()
        director = make_director(
            game_state=gs,
            route_response=_route_with_intent("TALK", _INTENT),
        )

        await director.act("go back to the forum and speak to the guard")

        narrator_call = director._cast.narrator.execute.call_args
        raw_outputs: TurnOutputs = narrator_call.kwargs["input_data"]
        assert raw_outputs.intent == _INTENT

    @allure.story("Turn intent")
    @allure.title("TurnOutputs.intent stays None when the routing plan omits the field")
    @pytest.mark.asyncio
    async def test_plan_without_intent_leaves_turn_outputs_intent_none(self):
        gs = make_game_state()
        director = make_director(
            game_state=gs,
            route_response={
                "action_type": "TALK",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            },
        )

        await director.act("say hi")

        narrator_call = director._cast.narrator.execute.call_args
        raw_outputs: TurnOutputs = narrator_call.kwargs["input_data"]
        assert raw_outputs.intent is None
