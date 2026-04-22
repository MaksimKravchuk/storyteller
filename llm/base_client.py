from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from llm.message import Message, LLMResponse, Tool


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

    Three modes are mutually exclusive at the response-shape level:

    - ``response_format`` — legacy provider-specific dict (e.g.
      ``{"type": "json_object"}`` for OpenAI's JSON mode).
    - ``schema`` / ``schema_name`` — strict structured outputs (Pydantic
      ``model_json_schema()`` compatible). When set, the provider MUST
      honor it or raise ``NotImplementedError``.

    ``tools`` / ``tool_choice`` are orthogonal: a tool-use call normally
    leaves ``response_format`` / ``schema`` unset since the model's output
    arrives on :attr:`llm.message.LLMResponse.tool_calls`. ``tool_choice``
    accepts ``"auto"`` (model picks), ``"required"`` (model must call any
    tool), or a tool name (model must call that specific tool).
    """

    response_format: dict[str, Any] | None = None
    schema: dict[str, Any] | None = None
    schema_name: str | None = None
    tools: tuple[Tool, ...] | None = None
    tool_choice: str | None = None

    @property
    def is_strict(self) -> bool:
        """True when this format requests strict, schema-validated output."""
        return self.schema is not None

    @property
    def has_tools(self) -> bool:
        """True when tool definitions are attached to this call."""
        return bool(self.tools)


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

        ``output_format`` bundles three orthogonal concerns:

        - Legacy JSON mode (``response_format``) and strict structured
          outputs (``schema`` / ``schema_name``): when ``output_format.is_strict``
          is true the provider MUST honor the schema or raise
          ``NotImplementedError`` so callers can fall back.
        - Tool calls (``tools`` / ``tool_choice``): when present, the
          provider exposes the tools and translates ``tool_choice`` to its
          native shape. Results arrive on :attr:`LLMResponse.tool_calls`
          with already-decoded argument dicts.
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
