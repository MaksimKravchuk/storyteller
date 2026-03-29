from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a specific LLM model."""

    provider: str  # "openai", "anthropic", etc.
    model_id: str  # "gpt-4", "claude-sonnet-4-20250514", etc.
    temperature: float = 0.7
    max_tokens: int = 2048


class AI_MODELS:
    """Registry of available model configurations."""

    GPT_4 = ModelConfig(provider="openai", model_id="gpt-4")
    GPT_3_5_TURBO = ModelConfig(provider="openai", model_id="gpt-3.5-turbo")
    CLAUDE_SONNET = ModelConfig(provider="anthropic", model_id="claude-sonnet-4-20250514")
    CLAUDE_HAIKU = ModelConfig(provider="anthropic", model_id="claude-haiku-4-20250514")
