from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from llm.base_client import BaseLLMClient
from llm.message import Message, LLMResponse


_ALLOWED_CONTROL = frozenset("\t\n\r")


def _is_printable(ch: str) -> bool:
    """Return True if the character is safe for JSON strings."""
    return (ch >= "\x20" and ch != "\x7f") or ch in _ALLOWED_CONTROL


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
    """OpenAI API provider (GPT-4, GPT-3.5-turbo, etc.)."""

    def __init__(
        self,
        model: str = "gpt-4",
        api_key: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        # Lazy import so openai is not required when using another provider
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=self.api_key)

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

        response = await self._client.chat.completions.create(**kwargs)
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
