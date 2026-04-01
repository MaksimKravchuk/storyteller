"""Base class for all theater agents (performers)."""

from __future__ import annotations

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
from loguru import logger
from prompts.base_template import PromptTemplate

_LOG_PREVIEW_CHARS = 200


def _try_bracket_extraction(raw: str) -> dict | None:
    """Attempt to extract JSON by finding outermost braces. Returns dict or None."""
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start:end])
    except json.JSONDecodeError:
        return None


def _parent_agent(stack: list[str] | None) -> str | None:
    """Return the parent agent name from the call stack, or None if at root."""
    if stack and len(stack) >= 2:  # noqa: WPS507
        return stack[-2]
    return None


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
        agent_name = type(self).__name__
        new_stack = list(agent_stack.get(None) or []) + [agent_name]
        token = agent_stack.set(new_stack)
        parent = _parent_agent(new_stack)
        start = time.monotonic()
        logger.info("agent={} parent={} | start", agent_name, parent)
        try:  # noqa: WPS501
            act_response = await self.act(input_data, context or {})
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "agent={} parent={} | error | exc_type={} | duration_ms={}",
                agent_name,
                parent,
                type(exc).__name__,
                duration_ms,
            )
            raise
        else:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info("agent={} parent={} | done | duration_ms={}", agent_name, parent, duration_ms)
            return act_response
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

        stack = agent_stack.get(None) or []
        parent = _parent_agent(stack)
        model = response.model or self.llm_client.model
        logger.info(
            "LLM | agent={} model={} parent={} | prompt_tokens={} completion_tokens={} duration_ms={}",
            type(self).__name__,
            model,
            parent,
            response.usage.get("prompt_tokens"),
            response.usage.get("completion_tokens"),
            duration_ms,
        )

        # Capture call for admin dashboard
        session_id = current_session_id.get(None)
        if session_id is not None:
            seq = call_sequence_counter.get(0)
            call_sequence_counter.set(seq + 1)
            buf = call_log_buffer.get(None) or []
            buf.append(
                {
                    "session_id": session_id,
                    "agent_name": type(self).__name__,
                    "model": model,
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
        _attempt: int = 0,
    ) -> dict:
        """Send a message expecting JSON back, with retry on parse failure."""
        total_attempts = retries + 1
        raw = await self._send(
            user_message,
            conversation=conversation,
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "LLM returned malformed JSON on attempt {}/{}: trying bracket extraction. Raw (first 200 chars): {}",
                _attempt + 1,
                total_attempts,
                raw[:_LOG_PREVIEW_CHARS],
            )
            if _attempt < retries:
                return await self._send_json(
                    user_message,
                    conversation=conversation,
                    retries=retries,
                    _attempt=_attempt + 1,
                )
            extracted = _try_bracket_extraction(raw)
            if extracted is not None:
                return extracted
            logger.warning(
                "Bracket extraction also failed on attempt {}/{}: raw (first {} chars): {}",
                _attempt + 1,
                total_attempts,
                _LOG_PREVIEW_CHARS,
                raw[:_LOG_PREVIEW_CHARS],
            )
            preview = raw[:_LOG_PREVIEW_CHARS]
            raise ValueError(
                "Agent failed to produce valid JSON after {0} attempts. Last response: {1}".format(
                    total_attempts, preview
                ),
            )
