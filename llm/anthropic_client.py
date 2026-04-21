from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from llm.base_client import BaseLLMClient, OutputFormat
from llm.message import Message, LLMResponse, Role

if TYPE_CHECKING:
    from anthropic import BadRequestError


_STRUCTURED_OUTPUT_REJECTION_MARKERS = (
    "structured output",
    "structured outputs",
    "json_schema",
    "output_format",
    "output_config",
)


def _extract_error_message(exc: "BadRequestError") -> str:
    """Return the human-readable message embedded in a BadRequestError body."""
    body = getattr(exc, "body", None) or {}
    if isinstance(body, dict):
        error = body.get("error") or {}
        if isinstance(error, dict):
            return str(error.get("message", ""))
    return ""


def _is_structured_output_rejection(exc: "BadRequestError") -> bool:
    """Return True when a 400 error indicates the model cannot honor the schema."""
    haystack = (_extract_error_message(exc) or str(exc)).lower()
    return any(marker in haystack for marker in _STRUCTURED_OUTPUT_REJECTION_MARKERS)


class AnthropicClient(BaseLLMClient):
    """Anthropic API provider (Claude models)."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        # Lazy import so anthropic is not required when using another provider
        from anthropic import AsyncAnthropic, BadRequestError

        self._client = AsyncAnthropic(api_key=self.api_key)
        # Stored as an instance attribute so ``except self._bad_request_error``
        # works without a top-level import of ``anthropic``.
        self._bad_request_error: type[BadRequestError] = BadRequestError

    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        output_format: OutputFormat | None = None,
    ) -> LLMResponse:
        formatted = self._format_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": formatted,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        if output_format is not None and output_format.is_strict:
            response = await self._send_with_schema(kwargs, output_format.schema or {})
        else:
            response = await self._client.messages.create(**kwargs)

        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text

        return LLMResponse(
            body=response_text,
            raw_response=response,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
            model=response.model,
        )

    async def send_message_streaming(
        self,
        messages: list[Message],
        system_prompt: str = "",
    ) -> AsyncIterator[str]:
        formatted = self._format_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": formatted,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def _send_with_schema(
        self,
        kwargs: dict[str, Any],
        json_schema: dict[str, Any],
    ) -> Any:
        """Issue a structured-outputs beta call, translating unsupported errors.

        Raises ``NotImplementedError`` when the API returns a 400 indicating
        the model or endpoint does not support structured outputs, so callers
        can degrade to the prompt-based JSON path.
        """
        kwargs["output_format"] = {"type": "json_schema", "schema": json_schema}
        try:
            return await self._client.beta.messages.create(**kwargs)
        except self._bad_request_error as exc:
            if _is_structured_output_rejection(exc):
                raise NotImplementedError(
                    "structured outputs not supported for model={0}".format(self.model),
                ) from exc
            raise

    def _format_messages(self, messages: list[Message]) -> list[dict[str, str]]:
        """Format messages for the Anthropic API.

        Note: Anthropic uses a separate ``system`` parameter rather than a
        system message inside the messages list.
        """
        formatted: list[dict[str, str]] = []
        for msg in messages:
            # Map our Role enum to Anthropic role strings
            role = "user" if msg.role == Role.USER else "assistant"
            formatted.append({"role": role, "content": msg.body})
        return formatted
