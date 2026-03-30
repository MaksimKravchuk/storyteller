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

    gpt_4 = ModelConfig(provider="openai", model_id="gpt-4")
    gpt_3_5_turbo = ModelConfig(provider="openai", model_id="gpt-3.5-turbo")
    claude_sonnet = ModelConfig(provider="anthropic", model_id="claude-sonnet-4-20250514")
    claude_haiku = ModelConfig(provider="anthropic", model_id="claude-haiku-4-20250514")
