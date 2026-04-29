"""Base class for all theater agents (performers)."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, TypeVar, overload

from cast._performer_retry import RetryContext as _RetryContext, _strip_markdown_fence
from llm.base_client import BaseLLMClient, LLMJSONError, OutputFormat
from llm.call_logger import (
    agent_stack,
    call_log_buffer,
    current_session_id,
    next_sequence,
)
from llm.message import LLMResponse, Message, Role, Tool, ToolCall
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


_TOOL_CALL_LOG_TEMPLATE = "[tool:{0}] {1}"


def _render_response_content(response: LLMResponse) -> str:
    """Render the dashboard's ``response_content`` string from a response.

    Pure prose responses return their body unchanged. Tool calls are
    rendered as ``[tool:<name>] {<json-args>}`` lines, newline-joined,
    and prepended to any body prose so the admin log stays useful
    without a new column.
    """
    if not response.tool_calls:
        return response.body
    tool_lines = [
        _TOOL_CALL_LOG_TEMPLATE.format(
            call.name,
            json.dumps(call.arguments, ensure_ascii=False, default=str),
        )
        for call in response.tool_calls
    ]
    joined = "\n".join(tool_lines)
    if response.body:
        return "{0}\n{1}".format(joined, response.body)
    return joined


def _record_llm_call(
    agent_name: str,
    model: str,
    response: LLMResponse,
    system_prompt: str,
    messages: list[Message],
) -> None:
    """Log the LLM call and capture details for the admin dashboard."""
    stack = agent_stack.get(None) or []
    parent = stack[-2] if len(stack) >= 2 else None
    logger.info(
        "LLM | agent={} model={} parent={} | prompt_tokens={} completion_tokens={} duration_ms={}",
        agent_name,
        model,
        parent,
        response.usage.get("prompt_tokens"),
        response.usage.get("completion_tokens"),
        response.usage.get("duration_ms", 0),
    )
    session_id = current_session_id.get(None)
    if session_id is None:
        return
    buf = call_log_buffer.get(None) or []
    buf.append(
        {
            "session_id": session_id,
            "agent_name": agent_name,
            "model": model,
            "system_prompt": system_prompt,
            "messages": [{"role": msg.role.value, "content": msg.body} for msg in messages],
            "response_content": _render_response_content(response),
            "prompt_tokens": response.usage.get("prompt_tokens"),
            "completion_tokens": response.usage.get("completion_tokens"),
            "parent_agent": parent,
            "call_sequence": next_sequence(),
        }
    )
    call_log_buffer.set(buf)


async def _retry_after_validation_failure(
    performer: BasePerformer,
    ctx: _RetryContext,
    assistant_text: str,
    exc: ValidationError,
) -> Any:
    """Retry with validation feedback or raise after exhausting attempts.

    Used only by the prompt-based fallback path. The strict path raises
    immediately on validation failure because the provider guaranteed the
    shape — a failure there indicates a deeper bug, not a recoverable miss.
    """
    errors_preview = str(exc.errors())[:_VALIDATION_ERROR_PREVIEW_CHARS]
    logger.warning(
        "LLM JSON failed schema validation on attempt {}/{}: {}",
        ctx.attempt + 1,
        ctx.retries + 1,
        errors_preview,
    )
    if ctx.attempt >= ctx.retries:
        raise LLMJSONError(
            "Agent failed schema validation after {0} attempts. Errors: {1}".format(
                ctx.retries + 1,
                errors_preview,
            ),
            raw_response=assistant_text,
        )
    retry_conversation = list(ctx.conversation or [])
    retry_conversation.append(Message(role=Role.ASSISTANT, body=assistant_text))
    retry_conversation.append(
        Message(
            role=Role.USER,
            body=_VALIDATION_FEEDBACK_TEMPLATE.format(exc.errors()),
        ),
    )
    retry_ctx = _RetryContext(
        user_message=ctx.user_message,
        conversation=retry_conversation,
        retries=ctx.retries,
        attempt=ctx.attempt + 1,
        response_model=ctx.response_model,
        max_tokens=ctx.max_tokens,
    )
    return await _send_json_prompt_fallback(performer, retry_ctx)


async def _send_json_prompt_fallback(performer: BasePerformer, ctx: _RetryContext) -> Any:
    """Prompt-based JSON path with validation-only retries (no decode retry).

    Module-level helper to keep ``BasePerformer`` from accumulating too many
    methods. Decode failures hard-raise ``LLMJSONError`` immediately — the
    bracket-extraction recovery has been removed.
    """
    raw = await performer._send(
        ctx.user_message,
        conversation=ctx.conversation,
        response_format={"type": "json_object"},
        max_tokens=ctx.max_tokens,
    )
    cleaned = _strip_markdown_fence(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        preview = raw[:_LOG_PREVIEW_CHARS]
        raise LLMJSONError(
            "Agent returned non-JSON response on fallback path: {0}".format(preview),
            raw_response=raw,
        ) from exc

    if ctx.response_model is None:
        return parsed

    try:
        return ctx.response_model.model_validate(parsed)
    except ValidationError as exc:
        return await _retry_after_validation_failure(performer, ctx, cleaned, exc)


async def _send_json_strict(
    performer: BasePerformer,
    user_message: str,
    conversation: list[Message] | None,
    response_model: type[BaseModelT],
    max_tokens: int | None = None,
) -> BaseModelT:
    """Run the strict structured-outputs path and validate the response.

    Module-level to keep the ``BasePerformer`` method count under the WPS
    limit. Raises ``NotImplementedError`` when the provider does not support
    strict structured outputs (caller falls back to the prompt path) and
    ``LLMJSONError`` when the provider returns text that does not match the
    schema (a contract violation, not a recoverable miss).
    """
    output_format = OutputFormat(
        schema=response_model.model_json_schema(),
        schema_name=response_model.__name__,
    )
    overrides = None if max_tokens is None else {"max_tokens": max_tokens}
    response = await _call_llm(
        performer,
        user_message=user_message,
        conversation=conversation,
        output_format=output_format,
        overrides=overrides,
    )
    raw = response.body
    try:
        return response_model.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMJSONError(
            "Strict structured output failed validation: {0}".format(exc),
            raw_response=raw,
        ) from exc


async def _call_llm(
    performer: BasePerformer,
    *,
    user_message: str,
    conversation: list[Message] | None,
    output_format: OutputFormat | None,
    overrides: dict[str, Any] | None = None,
) -> LLMResponse:
    """Single LLM-call site shared by ``_send``, ``_send_json``, and ``_send_tool``.

    Centralizing the call here keeps timing, output-format selection, and
    ``_record_llm_call`` bookkeeping consistent regardless of which public
    helper invoked the LLM. Lives at module level to keep the ``BasePerformer``
    method count under the WPS limit.

    Returns the full :class:`LLMResponse` so callers can read either
    ``response.body`` (text path) or ``response.tool_calls`` (tool path).
    ``overrides`` may contain ``temperature`` and/or ``max_tokens`` keys;
    they are forwarded to ``llm_client.send_message`` verbatim. Tool-use
    controls travel on ``output_format.tools`` / ``output_format.tool_choice``.
    """
    messages = list(conversation or [])
    messages.append(Message(role=Role.USER, body=user_message))
    system_prompt = performer.system_prompt_template.render(**performer._system_prompt_vars)

    call_kwargs: dict[str, Any] = {
        "messages": messages,
        "system_prompt": system_prompt,
        "output_format": output_format,
    }
    if overrides:
        call_kwargs.update(overrides)

    start = time.monotonic()
    response: LLMResponse = await performer.llm_client.send_message(**call_kwargs)
    response.usage["duration_ms"] = int((time.monotonic() - start) * 1000)

    _record_llm_call(
        type(performer).__name__,
        response.model or performer.llm_client.model,
        response,
        system_prompt,
        messages,
    )
    return response


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
        existing_stack = agent_stack.get(None) or []
        new_stack = list(existing_stack) + [type(self).__name__]
        token = agent_stack.set(new_stack)
        start = time.monotonic()
        logger.info(
            "agent={} parent={} | start",
            new_stack[-1],
            new_stack[-2] if len(new_stack) >= 2 else None,
        )
        try:
            act_response = await self.act(input_data, context or {})
        except Exception as exc:
            logger.exception(
                "agent={} parent={} | error | exc_type={} | duration_ms={}",
                new_stack[-1],
                new_stack[-2] if len(new_stack) >= 2 else None,
                type(exc).__name__,
                int((time.monotonic() - start) * 1000),
            )
            raise
        else:
            logger.info(
                "agent={} parent={} | done | duration_ms={}",
                new_stack[-1],
                new_stack[-2] if len(new_stack) >= 2 else None,
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
        output_format = OutputFormat(response_format=response_format) if response_format else None
        overrides: dict[str, Any] = {}
        if temperature is not None:
            overrides["temperature"] = temperature
        if max_tokens is not None:
            overrides["max_tokens"] = max_tokens
        response = await _call_llm(
            self,
            user_message=user_message,
            conversation=conversation,
            output_format=output_format,
            overrides=overrides or None,
        )
        return response.body

    async def _send_tool(
        self,
        user_message: str,
        tools: list[Tool],
        conversation: list[Message] | None = None,
    ) -> ToolCall:
        """Send a message and expect the LLM to invoke one of the provided tools.

        Returns the first tool call on the response. Raises
        :class:`LLMJSONError` (with the prose body as ``raw_response``)
        when the model returned prose instead of a tool call, so the
        caller can surface the failure the same way other routing
        miscommunications are handled.
        """
        output_format = OutputFormat(tools=tuple(tools), tool_choice="required")
        response = await _call_llm(
            self,
            user_message=user_message,
            conversation=conversation,
            output_format=output_format,
        )
        if not response.tool_calls:
            raise LLMJSONError(
                "Agent returned no tool call when one was required.",
                raw_response=response.body,
            )
        return response.tool_calls[0]

    @overload
    async def _send_json(
        self,
        user_message: str,
        conversation: list[Message] | None = ...,
        retries: int = ...,
        *,
        response_model: type[BaseModelT],
        max_tokens: int | None = ...,
    ) -> BaseModelT: ...

    @overload
    async def _send_json(
        self,
        user_message: str,
        conversation: list[Message] | None = ...,
        retries: int = ...,
        response_model: None = ...,
        max_tokens: int | None = ...,
    ) -> dict: ...

    async def _send_json(
        self,
        user_message: str,
        conversation: list[Message] | None = None,
        retries: int = 2,
        response_model: type[BaseModelT] | None = None,
        max_tokens: int | None = None,
    ) -> dict | BaseModelT:
        """Send a message expecting JSON back, preferring strict structured outputs.

        When ``response_model`` is provided, the strict path runs first: the
        Pydantic schema is sent to the provider and the response is guaranteed
        to match the shape (any deviation raises ``LLMJSONError`` with no
        retry). If the provider raises ``NotImplementedError``, the call
        degrades to the prompt-based fallback path.

        Without ``response_model`` the prompt-based fallback path runs:
        ``response_format`` ``{"type": "json_object"}`` is requested, the
        response is parsed with ``json.loads`` (decode failures raise
        ``LLMJSONError`` immediately — there is no bracket-extraction recovery
        anymore), and on ``ValidationError`` the conversation is appended
        with the assistant's bad response and a user feedback message
        before retrying.
        """
        if response_model is not None:
            try:
                return await _send_json_strict(
                    self,
                    user_message,
                    conversation,
                    response_model,
                    max_tokens=max_tokens,
                )
            except NotImplementedError:
                logger.info(
                    "Strict structured outputs unavailable for {}; falling back to prompt-based JSON",
                    type(self).__name__,
                )

        ctx = _RetryContext(
            user_message=user_message,
            conversation=conversation,
            retries=retries,
            attempt=0,
            response_model=response_model,
            max_tokens=max_tokens,
        )
        return await _send_json_prompt_fallback(self, ctx)
