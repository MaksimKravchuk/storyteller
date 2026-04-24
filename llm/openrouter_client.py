"""OpenRouter provider — OpenAI-compatible gateway to DeepSeek/Gemini/Grok/etc."""

from __future__ import annotations

from typing import Any

from llm.openai_client import OpenAIClient

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_REFERER = "https://storyteller.local"
_OPENROUTER_APP_TITLE = "Storyteller"


class OpenRouterClient(OpenAIClient):
    """OpenRouter API provider.

    OpenRouter exposes an OpenAI-compatible Chat Completions API at a
    different ``base_url`` and proxies requests to the selected upstream
    model (``deepseek/...``, ``google/...``, ``x-ai/...``, etc.). All
    request translation, JSON-schema normalisation, tool wiring, and
    error logging are inherited from :class:`OpenAIClient`; we only
    swap the underlying ``AsyncOpenAI`` client with one pointed at
    OpenRouter and add the attribution headers OpenRouter recommends.

    Note: strict schema enforcement depends on the upstream model.
    Some OpenRouter backends silently ignore ``response_format`` with
    ``strict=True``; operators should verify via the admin UI before
    wiring a model to a JSON-heavy role (e.g. Director).
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        # Replace the parent-constructed OpenAI client with one pointed at
        # OpenRouter. Lazy import keeps openai optional for other providers.
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=_OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": _OPENROUTER_REFERER,
                "X-Title": _OPENROUTER_APP_TITLE,
            },
        )
