from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from llm.message import Message, LLMResponse


class LLMJSONError(ValueError):
    """Raised when an LLM fails to produce valid JSON / schema after retries.

    Carries the last raw response so callers can log it or use it as a
    salvage narration (see cast.actor.Actor.act's envelope-failure fallback).
    """

    def __init__(self, message: str, raw_response: str):
        super().__init__(message)
        self.raw_response = raw_response


@dataclass(frozen=True)
class OutputFormat:
    """Output-shape controls for a single LLM call.

    ``response_format`` is the legacy provider-specific dict (e.g.
    ``{"type": "json_object"}`` for OpenAI's JSON mode). ``schema`` and
    ``schema_name`` request strict, schema-validated output through the
    provider's structured-outputs surface (the schema is a Pydantic
    ``model_json_schema()``). The two modes are mutually exclusive — when
    ``schema`` is set, the provider MUST honor it (or raise
    ``NotImplementedError``) and ignore ``response_format``.
    """

    response_format: dict[str, Any] | None = None
    schema: dict[str, Any] | None = None
    schema_name: str | None = None

    @property
    def is_strict(self) -> bool:
        """True when this format requests strict, schema-validated output."""
        return self.schema is not None


class BaseLLMClient(ABC):
    """Provider-agnostic LLM interface.

    All agents talk to LLMs through this abstraction.
    Concrete implementations live in openai_client.py, anthropic_client.py, etc.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        output_format: OutputFormat | None = None,
    ) -> LLMResponse:
        """Send messages and return the model response.

        When ``output_format.is_strict`` is true, the provider MUST request
        strict, schema-validated output from its API. If the provider or
        pinned model does not support strict structured outputs, it MUST
        raise ``NotImplementedError`` so callers can fall back to prompt-
        based JSON.
        """
        ...

    @abstractmethod
    async def send_message_streaming(
        self,
        messages: list[Message],
        system_prompt: str = "",
    ) -> AsyncIterator[str]:
        """Stream response tokens.

        Raise ``NotImplementedError`` if the provider does not support streaming.
        """
        ...
