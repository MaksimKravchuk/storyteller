from __future__ import annotations

from abc import ABC, abstractmethod

from llm.message import LLMResponse, Message, OutputFormat


class LLMJSONError(ValueError):
    """Raised when an LLM fails to produce valid JSON / schema after retries.

    Carries the last raw response so callers can log it or use it as a
    salvage narration (see cast.actor.Actor.act's envelope-failure fallback).
    """

    def __init__(self, message: str, raw_response: str):
        super().__init__(message)
        self.raw_response = raw_response


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
        supports_structured_output: bool = True,
    ):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.supports_structured_output = supports_structured_output

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
          outputs (``schema`` / ``schema_name``): when ``output_format.schema``
          is not None the provider MUST honor the schema or raise
          ``NotImplementedError`` so callers can fall back.
        - Tool calls (``tools`` / ``tool_choice``): when present, the
          provider exposes the tools and translates ``tool_choice`` to its
          native shape. Results arrive on :attr:`LLMResponse.tool_calls`
          with already-decoded argument dicts.
        """
        ...
