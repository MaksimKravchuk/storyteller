from __future__ import annotations

import asyncio
import functools
import types
from typing import TYPE_CHECKING, Any

from defaults.models import (
    PROVIDER_ANTHROPIC,
    PROVIDER_DEEPSEEK,
    PROVIDER_OPENAI,
    PROVIDER_OPENROUTER,
    ModelConfig,
)

if TYPE_CHECKING:
    from llm.base_client import BaseLLMClient

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_HEADERS: types.MappingProxyType[str, str] = types.MappingProxyType(
    {
        "HTTP-Referer": "https://storyteller.local",
        "X-Title": "Storyteller",
    },
)
_CLIENT_CACHE_SIZE = 32
_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def create_llm_client(
    config: ModelConfig,
    api_key: str | None = None,
) -> "BaseLLMClient":
    """Return the process-wide LLM client for ``(config, api_key)``, creating it on first use.

    Each SDK client owns an HTTP connection pool, so rebuilding one per turn meant fresh TLS
    handshakes every turn. The cache is keyed by the running event loop too, because a pooled
    httpx client must not outlive its loop (benchmarks and tests call ``asyncio.run`` repeatedly).
    If ``api_key`` is None the underlying SDK falls back to its own environment-variable
    detection (``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY``).
    """
    return _cached_client(config, api_key, _running_loop())


@functools.lru_cache(maxsize=_CLIENT_CACHE_SIZE)
def _cached_client(
    config: ModelConfig,
    api_key: str | None,
    loop: asyncio.AbstractEventLoop | None,
) -> "BaseLLMClient":
    """Memoised ``_build_llm_client``; ``loop`` only widens the cache key."""
    return _build_llm_client(config, api_key)


def _build_llm_client(
    config: ModelConfig,
    api_key: str | None = None,
) -> "BaseLLMClient":
    """Create the right LLM client for a given ModelConfig (uncached)."""
    if config.provider == PROVIDER_ANTHROPIC:
        from llm.anthropic_client import AnthropicClient

        return AnthropicClient(
            model=config.model_id,
            api_key=api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            supports_structured_output=config.supports_structured_output,
        )

    from llm.openai_client import OpenAIClient

    extra: dict[str, Any] = {}
    if config.provider == PROVIDER_OPENROUTER:
        extra["base_url"] = _OPENROUTER_BASE_URL
        extra["extra_headers"] = _OPENROUTER_HEADERS
    elif config.provider == PROVIDER_DEEPSEEK:
        extra["base_url"] = _DEEPSEEK_BASE_URL
    elif config.provider != PROVIDER_OPENAI:
        raise ValueError(f"Unknown LLM provider: {config.provider}")

    return OpenAIClient(
        model=config.model_id,
        api_key=api_key,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        **extra,
    )
