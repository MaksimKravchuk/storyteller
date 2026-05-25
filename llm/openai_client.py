from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any

from loguru import logger

from llm._openai_tools import (
    _StrictSchemaNormalizer,
    _build_wire_tool_choice,
    _build_wire_tools,
    _parse_response_tool_calls,
)
from llm.base_client import BaseLLMClient, OutputFormat
from llm.message import LLMResponse, Message

if TYPE_CHECKING:
    from openai import APIStatusError


_ALLOWED_CONTROL = frozenset("\t\n\r")
_SYSTEM_PROMPT_LOG_CHARS = 200

# Bounded backoff for OpenAI 5xx and transient network errors. Mirrors the
# shape of ``llm.anthropic_client._call_with_retry`` for provider parity.
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY = 2.0


async def _call_with_retry(
    create: Callable[[], Awaitable[Any]],
    max_attempts: int = _RETRY_MAX_ATTEMPTS,
    base_delay: float = _RETRY_BASE_DELAY,
    attempt: int = 0,
) -> Any:
    """Invoke ``create`` with bounded exponential backoff on OpenAI 5xx and transient errors.

    Retries on :class:`openai.InternalServerError` (5xx) and
    :class:`openai.APIConnectionError` (includes :class:`openai.APITimeoutError`).
    Backoff is ``base_delay * 2**attempt``. Other errors (4xx, validation) propagate
    immediately. Implemented via tail recursion so the retry loop carries its own
    attempt counter without an ``await`` inside a ``for`` loop body.
    """
    from cast import _reliability_metrics
    from openai import APIConnectionError, InternalServerError

    try:
        return await create()
    except (InternalServerError, APIConnectionError) as exc:
        if attempt + 1 >= max_attempts:
            raise
        delay = base_delay * (2**attempt)
        _reliability_metrics.record_retry("openai_client", attempt + 1)
        logger.warning(
            "OpenAI transient error (attempt {}/{}); retrying in {}s: {}",
            attempt + 1,
            max_attempts,
            delay,
            exc,
        )
        await asyncio.sleep(delay)
    return await _call_with_retry(create, max_attempts, base_delay, attempt + 1)


def _is_printable(ch: str) -> bool:
    """Return True if the character is safe for JSON strings."""
    return (ch >= "\x20" and ch != "\x7f") or ch in _ALLOWED_CONTROL


def _build_response_format(output_format: OutputFormat | None) -> dict[str, Any] | None:
    """Translate an ``OutputFormat`` into the OpenAI ``response_format`` payload.

    Returns ``None`` when the caller did not request any specific format.
    Strict mode (``output_format.schema is not None``) wins over the legacy dict.
    """
    if output_format is None:
        return None
    if output_format.schema is not None:
        return _StrictSchemaNormalizer.wrap(
            output_format.schema,
            output_format.schema_name or "Response",
        )
    return output_format.response_format


def _extract_error_body(exc: Any) -> Any:
    """Return the structured body from an OpenAI ``APIStatusError``, or str(exc)."""
    return getattr(exc, "body", None) or str(exc)


def _sanitize(text: str) -> str:
    """Strip characters that break JSON serialization or OpenAI's HTTP parser.

    Handles lone surrogates, null bytes, and other control characters
    (below 0x20 or 0x7F) that are illegal in JSON strings. Tab, newline,
    and carriage-return are preserved.
    """
    # Replace lone surrogates first
    cleaned = text.encode("utf-8", "surrogatepass").decode("utf-8", "replace")
    # Strip null bytes and other control characters illegal in JSON strings
    # Keep \t (0x09), \n (0x0A), \r (0x0D); remove everything else below 0x20 and 0x7F
    return "".join(ch for ch in cleaned if _is_printable(ch))


class OpenAIClient(BaseLLMClient):
    """OpenAI API provider (GPT-5.4 family, GPT-4o, etc.)."""

    def __init__(
        self,
        model: str = "gpt-5.4-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        # Lazy import so openai is not required when using another provider
        from openai import APIStatusError, AsyncOpenAI

        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if base_url is not None:
            client_kwargs["base_url"] = base_url
        if extra_headers:
            client_kwargs["default_headers"] = extra_headers
        self._client = AsyncOpenAI(**client_kwargs)
        # Stored as an instance attribute so ``except self._api_status_error``
        # works without a top-level import of ``openai``.
        self._api_status_error: type[APIStatusError] = APIStatusError

    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        output_format: OutputFormat | None = None,
    ) -> LLMResponse:
        kwargs = self._build_request_kwargs(
            messages,
            system_prompt,
            temperature,
            max_tokens,
            output_format,
        )
        try:
            response = await _call_with_retry(lambda: self._client.chat.completions.create(**kwargs))
        except self._api_status_error as exc:
            self._log_api_error(exc, kwargs, system_prompt)
            raise
        choice = response.choices[0]

        return LLMResponse(
            body=choice.message.content or "",
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            model=response.model,
            tool_calls=_parse_response_tool_calls(choice),
        )

    def _build_request_kwargs(
        self,
        messages: list[Message],
        system_prompt: str,
        temperature: float | None,
        max_tokens: int | None,
        output_format: OutputFormat | None,
    ) -> dict[str, Any]:
        """Build the kwargs dict handed to ``chat.completions.create``.

        Kept separate so :meth:`send_message` stays within the flake8
        local-variable budget; the translation logic lives here.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self._format_messages(messages, system_prompt),
            "temperature": self.temperature if temperature is None else temperature,
            "max_completion_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }
        wire_response_format = _build_response_format(output_format)
        if wire_response_format is not None:
            kwargs["response_format"] = wire_response_format
        if output_format is not None and output_format.tools:
            kwargs["tools"] = _build_wire_tools(output_format.tools)
            wire_tool_choice = _build_wire_tool_choice(output_format.tool_choice)
            if wire_tool_choice is not None:
                kwargs["tool_choice"] = wire_tool_choice
        return kwargs

    def _format_messages(
        self,
        messages: list[Message],
        system_prompt: str = "",
    ) -> list[dict[str, str]]:
        formatted: list[dict[str, str]] = []
        if system_prompt:
            formatted.append({"role": "system", "content": _sanitize(system_prompt)})
        for msg in messages:
            sanitized_body = _sanitize(msg.body)
            formatted.append({"role": msg.role.value, "content": sanitized_body})
        return formatted

    def _log_api_error(
        self,
        exc: "APIStatusError",
        kwargs: dict[str, Any],
        system_prompt: str,
    ) -> None:
        """Log the OpenAI error body so the caller can see what the API rejected."""
        logger.error(
            "OpenAI API error | model={} status={} "
            "has_response_format={} num_messages={} temperature={} "
            "max_completion_tokens={} system_prompt[:{}]={!r} body={!r}",
            self.model,
            getattr(exc, "status_code", None),
            "response_format" in kwargs,
            len(kwargs.get("messages", [])),
            kwargs.get("temperature"),
            kwargs.get("max_completion_tokens"),
            _SYSTEM_PROMPT_LOG_CHARS,
            system_prompt[:_SYSTEM_PROMPT_LOG_CHARS],
            _extract_error_body(exc),
        )
