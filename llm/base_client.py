from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from llm.message import Message, LLMResponse


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
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Send messages and return the model response."""
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
