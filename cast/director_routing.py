"""Action routing helpers for Director.

Uses provider tool calls to classify the player action. The LLM picks
exactly one of the verb tools (or the ``clarify`` tool) defined in
:mod:`cast.director_tools`; this module wraps the invocation, persists
the pending-clarification exchange across turns, and exposes the scene
history so the model has context on previous plans.
"""

from __future__ import annotations

import json as _json
from typing import Awaitable, Callable

from cast.director_tools import ACTION_TOOLS, RouteResult, parse_tool_call
from cast.schemas import action_plan as plan_schemas
from llm.message import Message, Role, Tool, ToolCall
from models.game_state import GameState
from prompts.base_template import PromptTemplate

_KEY_PLAYER_ACTION = "player_action"
_KEY_ACTION_TYPE = "action_type"
_DEFAULT_ACTION = "OTHER"


def _role_from_str(role_str: str) -> Role:
    """Map a serialised role string to a Role enum value."""
    return Role.USER if role_str == "user" else Role.ASSISTANT


def _msg_from_dict(msg: dict) -> Message:
    """Build a Message from a serialised dict."""
    return Message(role=_role_from_str(msg["role"]), body=msg["content"])


class ActionRouter:
    """Handles action classification and clarification flow."""

    def __init__(
        self,
        game_state: GameState,
        send_tool_fn: Callable[..., Awaitable[ToolCall]],
        action_routing_template: PromptTemplate,
    ) -> None:
        self._gs = game_state
        self._send_tool = send_tool_fn
        self._action_routing_template = action_routing_template
        self._tools: list[Tool] = list(ACTION_TOOLS)

    async def route_action(self, player_action: str) -> RouteResult:
        """Use the LLM to classify the action and return a typed plan.

        Invokes the provider's tool-call surface via ``_send_tool`` with
        the eight verb tools plus the clarify tool registered in
        :data:`cast.director_tools.ACTION_TOOLS`. The provider enforces
        the enum at the schema level, so misspellings and off-spec
        values can no longer leak through. Returns one of the eight
        verb plan classes on a routing call, or
        :class:`ClarificationRequest` when the model needs more info.
        """
        history = self.load_pending_clarification()
        if history:
            scene_history = self.build_scene_history() or []
            call = await self._send_tool(
                player_action,
                tools=self._tools,
                conversation=scene_history + history,
            )
        else:
            prompt = self._action_routing_template.render(player_action=player_action)
            call = await self._send_tool(
                prompt,
                tools=self._tools,
                conversation=self.build_scene_history(),
            )
        return parse_tool_call(call)

    def save_pending_clarification(
        self,
        player_action: str,
        request: plan_schemas.ClarificationRequest,
    ) -> None:
        """Persist a clarification exchange in game state.

        The persisted shape is a JSON-encoded dict so existing saved
        sessions keep deserialising cleanly.
        """
        prompt = self._action_routing_template.render(player_action=player_action)
        self._gs.pending_clarification = [
            {"role": "user", "content": prompt},
            {
                "role": "assistant",
                "content": _json.dumps(request.model_dump(), ensure_ascii=False),
            },
        ]

    def load_pending_clarification(self) -> list[Message] | None:
        """Restore pending clarification from game state as Message objects."""
        raw = self._gs.pending_clarification
        if not raw:
            return None
        return [_msg_from_dict(msg) for msg in raw]

    def build_scene_history(self) -> list[Message] | None:
        """Build a conversation history from the current scene's log.

        Returns ``Message`` pairs (user action + assistant routing response)
        for the last 10 exchanges. The assistant messages are rendered
        in the legacy ``{"action_type", "result_summary"}`` JSON shape
        so the model sees the same conversational context the pre-tools
        pipeline produced.
        """
        log = self._gs.scene_conversation_log
        if not log:
            return None
        messages: list[Message] = []
        for entry in log[-10:]:
            messages.append(
                Message(
                    role=Role.USER,
                    body='Player action: "{0}"'.format(entry[_KEY_PLAYER_ACTION]),
                )
            )
            messages.append(
                Message(
                    role=Role.ASSISTANT,
                    body=_json.dumps(
                        {
                            _KEY_ACTION_TYPE: entry.get(_KEY_ACTION_TYPE, _DEFAULT_ACTION),
                            "result_summary": entry.get("response_summary", ""),
                        },
                        ensure_ascii=False,
                    ),
                )
            )
        return messages if messages else None
