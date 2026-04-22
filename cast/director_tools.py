"""Director action-routing tool definitions.

Builds one :class:`llm.tools.Tool` per action verb (plus a ``clarify``
tool) from the Pydantic models in :mod:`cast.schemas.action_plan`. The
Director exposes these to the LLM and the model picks exactly one; we
then dispatch the returned :class:`llm.tools.ToolCall` back into the
typed :data:`ActionPlan` union (or a :class:`ClarificationRequest`).

Keeping tool schemas single-source with their Pydantic models means an
argument rename on a verb is always reflected in the tool schema and
the runtime consumer at the same time.
"""

from __future__ import annotations

import types
from typing import Union

from pydantic import BaseModel

from cast.schemas import action_plan as plan
from llm.message import Tool, ToolCall

CLARIFY_TOOL_NAME = "clarify"

# Result of :func:`parse_tool_call`: one of the eight verb plan classes
# or a :class:`ClarificationRequest`. Kept as a named alias so consumers
# don't have to spell out the nine-member union.
RouteResult = Union[
    plan.MovePlan,
    plan.TalkPlan,
    plan.ExaminePlan,
    plan.InteractPlan,
    plan.SleepPlan,
    plan.WaitPlan,
    plan.ExplorePlan,
    plan.OtherPlan,
    plan.ClarificationRequest,
]

# Lowercase verb-tool name → Pydantic class. The LLM sees the lowercase
# tool name; the class's ``action_type`` literal is the uppercase enum
# that downstream consumers read. Frozen via MappingProxyType so static
# analysis doesn't flag a mutable module-level constant.
_VERB_MODELS: types.MappingProxyType[str, type[BaseModel]] = types.MappingProxyType(
    {
        "move": plan.MovePlan,
        "talk": plan.TalkPlan,
        "examine": plan.ExaminePlan,
        "interact": plan.InteractPlan,
        "sleep": plan.SleepPlan,
        "wait": plan.WaitPlan,
        "explore": plan.ExplorePlan,
        "other": plan.OtherPlan,
    },
)

_VERB_DESCRIPTIONS: types.MappingProxyType[str, str] = types.MappingProxyType(
    {
        "move": "Player moves to a new location or toward a target.",
        "talk": "Player addresses one or more NPCs.",
        "examine": "Player looks closely at an object, item, or NPC feature.",
        "interact": "Player physically interacts with an object or NPC.",
        "sleep": "Player sleeps, ending the scene.",
        "wait": "Player passes the turn without acting.",
        "explore": "Player looks around or surveys the surroundings (no move).",
        "other": "Player action does not fit any other verb.",
    },
)


def _build_verb_tools() -> tuple[Tool, ...]:
    """Materialise the eight verb tools from their Pydantic schemas."""
    return tuple(
        Tool(
            name=name,
            description=_VERB_DESCRIPTIONS[name],
            parameters_schema=model.model_json_schema(),
        )
        for name, model in _VERB_MODELS.items()
    )


_CLARIFY_TOOL = Tool(
    name=CLARIFY_TOOL_NAME,
    description=(
        "Ask the player for clarification when the action target is "
        "genuinely ambiguous. Do NOT use this to confirm intent or "
        "morality — accept the player's stated action as-is."
    ),
    parameters_schema=plan.ClarificationRequest.model_json_schema(),
)


ACTION_TOOLS: tuple[Tool, ...] = (*_build_verb_tools(), _CLARIFY_TOOL)


class UnknownToolError(ValueError):
    """Raised when the LLM calls a tool name outside the routing set."""


def parse_tool_call(call: ToolCall) -> RouteResult:
    """Validate and build the typed plan for a tool call returned by the LLM.

    Raises :class:`UnknownToolError` if the name is outside the registered
    set and :class:`pydantic.ValidationError` if the arguments do not
    match the verb schema. The strict tool-schema enforcement at the
    provider level makes validation errors rare in production, but the
    explicit re-validation here guards against hand-built ``ToolCall``
    instances (e.g. in tests).
    """
    if call.name == CLARIFY_TOOL_NAME:
        return plan.ClarificationRequest.model_validate(call.arguments)
    model = _VERB_MODELS.get(call.name)
    if model is None:
        raise UnknownToolError("Unknown routing tool: {0!r}".format(call.name))
    return model.model_validate(call.arguments)  # type: ignore[return-value]
