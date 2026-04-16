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

    gpt5_4_mini = ModelConfig(provider="openai", model_id="gpt-5.4-mini")
    gpt5_4_nano = ModelConfig(provider="openai", model_id="gpt-5.4-nano")
    gpt5_4_max = ModelConfig(provider="openai", model_id="gpt-5.4-max")
    claude_opus = ModelConfig(provider="anthropic", model_id="claude-opus-4-6")
    claude_sonnet = ModelConfig(provider="anthropic", model_id="claude-sonnet-4-20250514")
    claude_haiku = ModelConfig(provider="anthropic", model_id="claude-haiku-4-20250514")
