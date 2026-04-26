"""DeepSeek provider — OpenAI-compatible Chat Completions at api.deepseek.com."""

from __future__ import annotations

from typing import Any

from llm.openai_client import OpenAIClient

_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


class DeepSeekClient(OpenAIClient):
    """Native DeepSeek API provider.

    DeepSeek exposes an OpenAI-compatible Chat Completions API at
    ``api.deepseek.com``. Model ids are bare (``deepseek-chat``,
    ``deepseek-reasoner``) — no aggregator prefix. Translation, tool
    wiring, and error logging are inherited from :class:`OpenAIClient`;
    we only swap the underlying ``AsyncOpenAI`` client with one pointed
    at DeepSeek.

    Note: DeepSeek currently honours JSON-object mode but not OpenAI's
    strict JSON-schema validator, so :class:`OpenAIClient`'s strict
    ``response_format`` payload may be ignored by upstream. Operators
    pinning DeepSeek to JSON-heavy roles (e.g. Director) should verify
    output shape via the admin UI before wiring.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=_DEEPSEEK_BASE_URL,
        )
