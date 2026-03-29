"""Base class for all theater agents (performers)."""

from __future__ import annotations

import contextlib
import json
import time
from abc import ABC, abstractmethod
from typing import Any

from llm.base_client import BaseLLMClient
from llm.call_logger import (
    agent_stack,
    call_log_buffer,
    call_sequence_counter,
    current_session_id,
)
from llm.message import LLMResponse, Message, Role
from prompts.base_template import PromptTemplate


class BasePerformer(ABC):
    """Abstract base for every agent in the theater.

    Subclasses implement ``act()`` which is the agent's primary action.
    The base class provides helpers for building system prompts and
    sending messages through the LLM.
    """

    def __init__(
        self,
        *,
        llm_client: BaseLLMClient,
        system_prompt_template: PromptTemplate,
        tags: list[str] | None = None,
    ):
        self.llm_client = llm_client
        self.system_prompt_template = system_prompt_template
        self.tags: list[str] = tags or []
        self._system_prompt_vars: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    def set_context(self, **kwargs: str) -> None:
        """Set / update variables used to render the system prompt template."""
        self._system_prompt_vars.update(kwargs)

    # ------------------------------------------------------------------
    # Public entry-point (wraps act with call-chain tracking)
    # ------------------------------------------------------------------

    async def execute(self, input_data: Any, context: dict | None = None) -> Any:
        """Run this agent's ``act()`` while tracking the call chain.

        Pushes the agent name onto the shared stack so that any LLM call
        made inside ``act()`` records the correct ``parent_agent``.
        Uses a ContextVar token so the previous stack is restored exactly,
        even if ``act()`` raises.
        """
        new_stack = list(agent_stack.get(None) or []) + [type(self).__name__]
        token = agent_stack.set(new_stack)
        try:  # noqa: WPS501
            return await self.act(input_data, context or {})
        finally:
            agent_stack.reset(token)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def act(self, input_data: Any, context: dict) -> Any:
        """Perform this agent's primary action."""
        ...

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        return self.system_prompt_template.render(**self._system_prompt_vars)

    async def _send(
        self,
        user_message: str,
        conversation: list[Message] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a message through the LLM with this agent's system prompt.

        Returns the content string of the response.
        """
        messages = list(conversation or [])
        messages.append(Message(role=Role.USER, content=user_message))
        system_prompt = self._build_system_prompt()

        start = time.monotonic()
        response: LLMResponse = await self.llm_client.send_message(
            messages=messages,
            system_prompt=system_prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        # Capture call for admin dashboard logging
        session_id = current_session_id.get(None)
        if session_id is not None:
            stack = agent_stack.get(None) or []
            parent = stack[-2] if len(stack) >= 2 else None
            seq = call_sequence_counter.get(0)
            call_sequence_counter.set(seq + 1)

            buf = call_log_buffer.get(None) or []
            buf.append(
                {
                    "session_id": session_id,
                    "agent_name": type(self).__name__,
                    "model": response.model or self.llm_client.model,
                    "system_prompt": system_prompt,
                    "messages": [{"role": msg.role.value, "content": msg.content} for msg in messages],
                    "response_content": response.content,
                    "prompt_tokens": response.usage.get("prompt_tokens"),
                    "completion_tokens": response.usage.get("completion_tokens"),
                    "duration_ms": duration_ms,
                    "parent_agent": parent,
                    "call_sequence": seq,
                }
            )
            call_log_buffer.set(buf)

        return response.content

    async def _send_json(
        self,
        user_message: str,
        conversation: list[Message] | None = None,
        retries: int = 2,
    ) -> dict:
        """Send a message expecting JSON back, with retry on parse failure."""
        for attempt in range(retries + 1):
            raw = await self._send(
                user_message,
                conversation=conversation,
                response_format={"type": "json_object"},
            )
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                if attempt == retries:
                    # Last attempt: try to extract JSON from the response
                    start = raw.find("{")
                    end = raw.rfind("}") + 1
                    if start != -1 and end > start:
                        with contextlib.suppress(json.JSONDecodeError):
                            return json.loads(raw[start:end])
                    raise ValueError(
                        f"Agent failed to produce valid JSON after {retries + 1} attempts. Last response: {raw[:200]}"
                    )
        return {}  # unreachable
