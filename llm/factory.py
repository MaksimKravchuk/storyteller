from __future__ import annotations

from typing import TYPE_CHECKING

from defaults.models import (
    PROVIDER_ANTHROPIC,
    PROVIDER_DEEPSEEK,
    PROVIDER_OPENAI,
    PROVIDER_OPENROUTER,
    ModelConfig,
)
from llm.base_client import OutputFormat

if TYPE_CHECKING:
    from llm.base_client import BaseLLMClient


def json_object_format() -> OutputFormat:
    """Convenience: produce the OpenAI-style JSON-mode ``OutputFormat``.

    Exposed here so callers can request legacy prompt-based JSON mode without
    importing ``OutputFormat`` themselves (keeps module import counts small
    at call sites that only need one extra knob).
    """
    return OutputFormat(response_format={"type": "json_object"})


def _resolve_client_class(provider: str) -> type["BaseLLMClient"]:
    """Lazy-import and return the client class for ``provider``.

    Lazy imports keep optional SDKs (``openai``, ``anthropic``) out of the
    import graph for callers that only need one provider.
    """
    if provider == PROVIDER_OPENAI:
        from llm.openai_client import OpenAIClient

        return OpenAIClient
    if provider == PROVIDER_ANTHROPIC:
        from llm.anthropic_client import AnthropicClient

        return AnthropicClient
    if provider == PROVIDER_OPENROUTER:
        from llm.openrouter_client import OpenRouterClient

        return OpenRouterClient
    if provider == PROVIDER_DEEPSEEK:
        from llm.deepseek_client import DeepSeekClient

        return DeepSeekClient
    raise ValueError(f"Unknown LLM provider: {provider}")


def create_llm_client(
    config: ModelConfig,
    api_key: str | None = None,
) -> "BaseLLMClient":
    """Factory: create the right LLM client for a given ModelConfig.

    If ``api_key`` is None the underlying SDK will fall back to its own
    environment-variable detection (``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY``).
    """
    client_cls = _resolve_client_class(config.provider)
    return client_cls(
        model=config.model_id,
        api_key=api_key,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
