"""Base class for all theater agents (performers)."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypeVar, overload

from llm.base_client import BaseLLMClient
from llm.call_logger import (
    agent_stack,
    call_log_buffer,
    current_session_id,
    next_sequence,
)
from llm.message import LLMResponse, Message, Role
from loguru import logger
from prompts.base_template import PromptTemplate
from pydantic import BaseModel, ValidationError

_LOG_PREVIEW_CHARS = 200
_VALIDATION_ERROR_PREVIEW_CHARS = 400
_VALIDATION_FEEDBACK_TEMPLATE = (
    "Your JSON was structurally valid but failed schema validation:\n"
    "{0}\n"
    "Return the same response corrected to match the schema, as JSON only."
)

BaseModelT = TypeVar("BaseModelT", bound=BaseModel)


class LLMJSONError(ValueError):
    """Raised when an LLM fails to produce valid JSON / schema after retries.

    Carries the last raw response so callers can log it or use it as a
    salvage narration (see cast.actor.Actor.act's envelope-failure fallback).
    """

    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response


@dataclass(frozen=True)
class _RetryContext:
    """Parameters shared between attempts of a ``_send_json`` retry loop.

    Bundles the recursion state so the retry helpers don't need to take
    eight positional arguments each.
    """

    user_message: str
    conversation: list[Message] | None
    retries: int
    attempt: int
    response_model: type[BaseModel] | None

    @property
    def total_attempts(self) -> int:
        return self.retries + 1

    @property
    def can_retry(self) -> bool:
        return self.attempt < self.retries

    @classmethod
    def try_bracket_extraction(cls, raw: str) -> dict | None:
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
    if stack and stack[1:]:
        return stack[-2]
    return None


def _record_llm_call(
    agent_name: str,
    model: str,
    response: LLMResponse,
    system_prompt: str,
    messages: list[Message],
) -> None:
    """Log the LLM call and capture details for the admin dashboard."""
    parent = _parent_agent(agent_stack.get(None) or [])
    duration_ms = response.usage.get("duration_ms", 0)
    logger.info(
        "LLM | agent={} model={} parent={} | prompt_tokens={} completion_tokens={} duration_ms={}",
        agent_name,
        model,
        parent,
        response.usage.get("prompt_tokens"),
        response.usage.get("completion_tokens"),
        duration_ms,
    )
    session_id = current_session_id.get(None)
    if session_id is None:
        return
    seq = next_sequence()
    buf = call_log_buffer.get(None) or []
    buf.append(
        {
            "session_id": session_id,
            "agent_name": agent_name,
            "model": model,
            "system_prompt": system_prompt,
            "messages": [{"role": msg.role.value, "content": msg.body} for msg in messages],
            "response_content": response.body,
            "prompt_tokens": response.usage.get("prompt_tokens"),
            "completion_tokens": response.usage.get("completion_tokens"),
            "parent_agent": parent,
            "call_sequence": seq,
        }
    )
    call_log_buffer.set(buf)


async def _retry_after_decode_failure(
    performer: BasePerformer,
    ctx: _RetryContext,
    raw: str,
) -> Any:
    """Retry or raise after ``json.loads`` fails on an LLM response."""
    logger.warning(
        "LLM returned malformed JSON on attempt {}/{}: trying bracket extraction. Raw (first 200 chars): {}",
        ctx.attempt + 1,
        ctx.total_attempts,
        raw[:_LOG_PREVIEW_CHARS],
    )
    if ctx.can_retry:
        return await performer._send_json(
            ctx.user_message,
            conversation=ctx.conversation,
            retries=ctx.retries,
            _attempt=ctx.attempt + 1,
            response_model=ctx.response_model,
        )
    extracted = ctx.try_bracket_extraction(raw)
    if extracted is not None:
        if ctx.response_model is None:
            return extracted
        try:
            return ctx.response_model.model_validate(extracted)
        except ValidationError as exc:
            logger.warning(
                "Bracket-extracted JSON failed schema validation: {}",
                str(exc)[:_VALIDATION_ERROR_PREVIEW_CHARS],
            )
    logger.warning(
        "Bracket extraction also failed on attempt {}/{}: raw (first {} chars): {}",
        ctx.attempt + 1,
        ctx.total_attempts,
        _LOG_PREVIEW_CHARS,
        raw[:_LOG_PREVIEW_CHARS],
    )
    preview = raw[:_LOG_PREVIEW_CHARS]
    raise LLMJSONError(
        "Agent failed to produce valid JSON after {0} attempts. Last response: {1}".format(
            ctx.total_attempts,
            preview,
        ),
        raw_response=raw,
    )


async def _retry_after_validation_failure(
    performer: BasePerformer,
    ctx: _RetryContext,
    raw: str,
    exc: ValidationError,
) -> Any:
    """Retry with validation feedback or raise after exhausting attempts."""
    errors_preview = str(exc.errors())[:_VALIDATION_ERROR_PREVIEW_CHARS]
    logger.warning(
        "LLM JSON failed schema validation on attempt {}/{}: {}",
        ctx.attempt + 1,
        ctx.total_attempts,
        errors_preview,
    )
    if not ctx.can_retry:
        raise LLMJSONError(
            "Agent failed schema validation after {0} attempts. Errors: {1}".format(
                ctx.total_attempts,
                errors_preview,
            ),
            raw_response=raw,
        )
    retry_conversation = list(ctx.conversation or [])
    retry_conversation.append(Message(role=Role.ASSISTANT, body=raw))
    retry_conversation.append(
        Message(
            role=Role.USER,
            body=_VALIDATION_FEEDBACK_TEMPLATE.format(exc.errors()),
        ),
    )
    return await performer._send_json(
        ctx.user_message,
        conversation=retry_conversation,
        retries=ctx.retries,
        _attempt=ctx.attempt + 1,
        response_model=ctx.response_model,
    )


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
        current_stack = agent_stack.get(None) or []
        new_stack = list(current_stack) + [type(self).__name__]
        token = agent_stack.set(new_stack)
        start = time.monotonic()
        logger.info("agent={} parent={} | start", new_stack[-1], _parent_agent(new_stack))
        try:
            act_response = await self.act(input_data, context or {})
        except Exception as exc:
            logger.exception(
                "agent={} parent={} | error | exc_type={} | duration_ms={}",
                new_stack[-1],
                _parent_agent(new_stack),
                type(exc).__name__,
                int((time.monotonic() - start) * 1000),
            )
            raise
        else:
            logger.info(
                "agent={} parent={} | done | duration_ms={}",
                new_stack[-1],
                _parent_agent(new_stack),
                int((time.monotonic() - start) * 1000),
            )
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
        messages.append(Message(role=Role.USER, body=user_message))
        system_prompt = self._build_system_prompt()

        start = time.monotonic()
        response: LLMResponse = await self.llm_client.send_message(
            messages=messages,
            system_prompt=system_prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        response.usage["duration_ms"] = int((time.monotonic() - start) * 1000)

        model = response.model or self.llm_client.model
        _record_llm_call(type(self).__name__, model, response, system_prompt, messages)

        return response.body

    @overload
    async def _send_json(
        self,
        user_message: str,
        conversation: list[Message] | None = ...,
        retries: int = ...,
        _attempt: int = ...,
        *,
        response_model: type[BaseModelT],
    ) -> BaseModelT: ...

    @overload
    async def _send_json(
        self,
        user_message: str,
        conversation: list[Message] | None = ...,
        retries: int = ...,
        _attempt: int = ...,
        response_model: None = ...,
    ) -> dict: ...

    async def _send_json(
        self,
        user_message: str,
        conversation: list[Message] | None = None,
        retries: int = 2,
        _attempt: int = 0,
        response_model: type[BaseModelT] | None = None,
    ) -> dict | BaseModelT:
        """Send a message expecting JSON back, with self-correcting retries.

        The ``retries`` budget is shared between two failure modes:

        1. ``json.JSONDecodeError`` — the LLM returned text that does
           not parse as JSON. The prompt is re-sent unchanged. If the
           final attempt still fails, an outermost-braces extraction
           fallback is tried before raising.
        2. ``pydantic.ValidationError`` (only when ``response_model``
           is provided) — the JSON parsed cleanly but did not match the
           schema. A copy of the conversation is made (the caller's
           list is never mutated) and appended with the assistant's
           bad response and a user message containing the validation
           errors, asking the LLM to correct it.

        A single call therefore gets at most ``retries + 1`` attempts
        in total, regardless of which failure mode each attempt hits.

        When ``response_model`` is ``None``, this method returns the
        parsed dict — preserving the pre-refactor behaviour. When a
        schema is supplied, it returns a validated instance of that
        schema.
        """
        ctx = _RetryContext(
            user_message=user_message,
            conversation=conversation,
            retries=retries,
            attempt=_attempt,
            response_model=response_model,
        )
        raw = await self._send(
            user_message,
            conversation=conversation,
            response_format={"type": "json_object"},
        )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return await _retry_after_decode_failure(self, ctx, raw)

        if response_model is None:
            return parsed

        try:
            return response_model.model_validate(parsed)
        except ValidationError as exc:
            return await _retry_after_validation_failure(self, ctx, raw, exc)
