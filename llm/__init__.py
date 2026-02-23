from __future__ import annotations

from defaults import ModelConfig


def create_llm_client(
    config: ModelConfig,
    api_key: str | None = None,
) -> "BaseLLMClient":
    """Factory: create the right LLM client for a given ModelConfig.

    If ``api_key`` is None the underlying SDK will fall back to its own
    environment-variable detection (``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY``).
    """
    from llm.base_client import BaseLLMClient

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
    else:
        raise ValueError(f"Unknown LLM provider: {config.provider}")
