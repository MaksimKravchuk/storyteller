"""Action routing helpers for Director."""

from __future__ import annotations

import json as _json
from typing import Awaitable, Callable

from llm.message import Message, Role
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
        send_json_fn: Callable[..., Awaitable[dict]],
        action_routing_template: PromptTemplate,
    ) -> None:
        self._gs = game_state
        self._send_json = send_json_fn
        self._action_routing_template = action_routing_template

    async def route_action(self, player_action: str) -> dict:
        """Use the LLM to classify the action and produce a routing plan."""
        history = self.load_pending_clarification()
        if history:
            scene_history = self.build_scene_history() or []
            return await self._send_json(
                player_action,
                conversation=scene_history + history,
            )
        prompt = self._action_routing_template.render(player_action=player_action)
        return await self._send_json(prompt, conversation=self.build_scene_history())

    def save_pending_clarification(self, player_action: str, routing_plan: dict) -> None:
        """Persist a clarification exchange in game state."""
        prompt = self._action_routing_template.render(player_action=player_action)
        self._gs.pending_clarification = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": _json.dumps(routing_plan, ensure_ascii=False)},
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
        for the last 10 exchanges.
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
