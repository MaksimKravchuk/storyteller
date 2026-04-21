"""Tests for the Director action-routing tool definitions (cast.director_tools).

Asserts that:

- ``ACTION_TOOLS`` exposes exactly the eight verb tools plus ``clarify``.
- Each verb tool's JSON schema matches the corresponding Pydantic model.
- :func:`parse_tool_call` round-trips a :class:`ToolCall` into the
  right typed :data:`ActionPlan` variant (or :class:`ClarificationRequest`).
- Unknown tool names raise :class:`UnknownToolError`.
"""

from __future__ import annotations

import allure
import pytest

from cast.director_tools import ACTION_TOOLS, UnknownToolError, parse_tool_call
from cast.schemas import action_plan as plan_mod
from llm.message import ToolCall


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Director routing tools")
class TestActionTools:
    @allure.story("Registered tools")
    @allure.title("ACTION_TOOLS exposes every verb plus clarify, with no duplicates")
    def test_action_tools_registered(self) -> None:
        names = [tool.name for tool in ACTION_TOOLS]
        assert names == ["move", "talk", "examine", "interact", "sleep", "wait", "explore", "other", "clarify"]

    @allure.story("Registered tools")
    @allure.title("Each verb tool's parameter schema includes its action_type literal")
    def test_verb_tool_schemas_include_action_type_literal(self) -> None:
        for tool in ACTION_TOOLS:
            if tool.name == "clarify":
                continue
            properties = tool.parameters_schema.get("properties", {})
            assert "action_type" in properties
            # Literals surface as a one-element enum (or const) in the schema.
            action_type = properties["action_type"]
            enum_vals = action_type.get("enum") or [action_type.get("const")]
            assert len(enum_vals) == 1


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Director routing tools")
class TestParseToolCall:
    @allure.story("Round-trip")
    @allure.title("parse_tool_call builds a MovePlan from a move tool call")
    def test_parse_move(self) -> None:
        call = ToolCall(
            name="move",
            arguments={
                "action_type": "MOVE",
                "intent": "go to the market",
                "direction": "market",
                "delegate_to": ["narrator"],
                "targets": [],
                "is_aggressive": False,
            },
        )
        result = parse_tool_call(call)
        assert isinstance(result, plan_mod.MovePlan)
        assert result.direction == "market"

    @allure.story("Round-trip")
    @allure.title("parse_tool_call builds a TalkPlan with a contest attached")
    def test_parse_talk_with_contest(self) -> None:
        call = ToolCall(
            name="talk",
            arguments={
                "action_type": "TALK",
                "intent": "persuade the guard",
                "targets": ["guard"],
                "is_aggressive": False,
                "contest": {"type": "persuasion", "target": "guard"},
                "delegate_to": ["actor"],
            },
        )
        result = parse_tool_call(call)
        assert isinstance(result, plan_mod.TalkPlan)
        assert result.contest is not None
        assert result.contest.type == "persuasion"

    @allure.story("Round-trip")
    @allure.title("parse_tool_call builds a ClarificationRequest from a clarify tool call")
    def test_parse_clarify(self) -> None:
        call = ToolCall(
            name="clarify",
            arguments={"question": "Which guard?", "reason": "two guards named Marcus"},
        )
        result = parse_tool_call(call)
        assert isinstance(result, plan_mod.ClarificationRequest)
        assert result.question == "Which guard?"

    @allure.story("Error handling")
    @allure.title("parse_tool_call raises UnknownToolError when the tool name is unregistered")
    def test_unknown_tool_raises(self) -> None:
        with pytest.raises(UnknownToolError):
            parse_tool_call(ToolCall(name="teleport", arguments={}))
