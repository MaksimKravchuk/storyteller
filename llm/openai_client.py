from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from loguru import logger

from llm.base_client import BaseLLMClient
from llm.message import Message, LLMResponse

if TYPE_CHECKING:
    from openai import APIStatusError


_ALLOWED_CONTROL = frozenset("\t\n\r")
_SYSTEM_PROMPT_LOG_CHARS = 200


def _is_printable(ch: str) -> bool:
    """Return True if the character is safe for JSON strings."""
    return (ch >= "\x20" and ch != "\x7f") or ch in _ALLOWED_CONTROL


def _extract_error_body(exc: Any) -> Any:
    """Return the richest available payload from an OpenAI ``APIStatusError``.

    Prefers the structured ``exc.body`` dict, falls back to the raw HTTP
    response text, and finally ``str(exc)``.
    """
    body = getattr(exc, "body", None)
    if body is not None:
        return body
    response = getattr(exc, "response", None)
    text = getattr(response, "text", None)
    return text or str(exc)


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
        **kwargs: Any,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        # Lazy import so openai is not required when using another provider
        from openai import APIStatusError, AsyncOpenAI

        self._client = AsyncOpenAI(api_key=self.api_key)
        # Stored as an instance attribute so ``except self._api_status_error``
        # works without a top-level import of ``openai``.
        self._api_status_error: type[APIStatusError] = APIStatusError

    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        formatted = self._format_messages(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": formatted,
            "temperature": self.temperature if temperature is None else temperature,
            "max_completion_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except self._api_status_error as exc:
            self._log_api_error(exc, kwargs, system_prompt)
            raise
        choice = response.choices[0]

        return LLMResponse(
            body=choice.message.content or "",
            raw_response=response,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            model=response.model,
        )

    async def send_message_streaming(
        self,
        messages: list[Message],
        system_prompt: str = "",
    ) -> AsyncIterator[str]:
        formatted = self._format_messages(messages, system_prompt)

        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=formatted,
            temperature=self.temperature,
            max_completion_tokens=self.max_tokens,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

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
        """Log the OpenAI error body so the caller can see what the API rejected.

        The whole emit is guarded so that a logging failure can never mask
        the original API error.
        """
        try:
            self._emit_api_error_log(exc, kwargs, system_prompt)
        except Exception:  # noqa: BLE001 - logging must never mask the real error
            logger.exception("Failed to serialize OpenAI API error for logging")

    def _emit_api_error_log(
        self,
        exc: "APIStatusError",
        kwargs: dict[str, Any],
        system_prompt: str,
    ) -> None:
        """Emit the structured error log entry for an OpenAI API failure."""
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
