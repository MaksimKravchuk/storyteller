from __future__ import annotations

from typing import TYPE_CHECKING

from defaults.models import ModelConfig
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


def create_llm_client(
    config: ModelConfig,
    api_key: str | None = None,
) -> "BaseLLMClient":
    """Factory: create the right LLM client for a given ModelConfig.

    If ``api_key`` is None the underlying SDK will fall back to its own
    environment-variable detection (``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY``).
    """
    if config.provider == "openai":
        from llm.openai_client import OpenAIClient

        return OpenAIClient(
            model=config.model_id,
            api_key=api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    elif config.provider == "anthropic":
        from llm.anthropic_client import AnthropicClient

        return AnthropicClient(
            model=config.model_id,
            api_key=api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    elif config.provider == "openrouter":
        from llm.openrouter_client import OpenRouterClient

        return OpenRouterClient(
            model=config.model_id,
            api_key=api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {config.provider}")
