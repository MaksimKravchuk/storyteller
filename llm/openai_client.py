from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from llm.base_client import BaseLLMClient
from llm.message import Message, LLMResponse, Role


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

    @staticmethod
    def _sanitize(text: str) -> str:
        """Strip lone surrogate characters that break UTF-8 JSON serialization."""
        return text.encode("utf-8", "surrogatepass").decode("utf-8", "replace")

    def _format_messages(
        self, messages: list[Message], system_prompt: str = ""
    ) -> list[dict[str, str]]:
        formatted: list[dict[str, str]] = []
        if system_prompt:
            formatted.append({"role": "system", "content": self._sanitize(system_prompt)})
        for msg in messages:
            formatted.append({"role": msg.role.value, "content": self._sanitize(msg.content)})
        return formatted

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
            "temperature": temperature if temperature is not None else self.temperature,
            "max_completion_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        return LLMResponse(
            content=choice.message.content or "",
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
