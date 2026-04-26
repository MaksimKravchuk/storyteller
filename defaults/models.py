from __future__ import annotations

from dataclasses import dataclass

PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_DEEPSEEK = "deepseek"


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a specific LLM model."""

    provider: str  # "openai", "anthropic", etc.
    model_id: str  # "gpt-4", "claude-sonnet-4-20250514", etc.
    temperature: float = 0.7
    max_tokens: int = 2048


class AI_MODELS:
    """Registry of available model configurations."""

    gpt5_4 = ModelConfig(provider=PROVIDER_OPENAI, model_id="gpt-5.4")
    gpt5_4_mini = ModelConfig(provider=PROVIDER_OPENAI, model_id="gpt-5.4-mini")
    gpt5_4_nano = ModelConfig(provider=PROVIDER_OPENAI, model_id="gpt-5.4-nano")
    claude_opus = ModelConfig(provider=PROVIDER_ANTHROPIC, model_id="claude-opus-4-6")
    claude_sonnet = ModelConfig(provider=PROVIDER_ANTHROPIC, model_id="claude-sonnet-4-20250514")
    claude_haiku = ModelConfig(provider=PROVIDER_ANTHROPIC, model_id="claude-haiku-4-5-20251001")
    # OpenRouter-routed models (cheaper alternatives, require OPENROUTER_API_KEY)
    deepseek_chat = ModelConfig(provider=PROVIDER_OPENROUTER, model_id="deepseek/deepseek-chat-v3.1")
    deepseek_v4_pro = ModelConfig(provider=PROVIDER_OPENROUTER, model_id="deepseek/deepseek-v4-pro")
    gemini_pro = ModelConfig(provider=PROVIDER_OPENROUTER, model_id="google/gemini-2.5-pro")
    gemini_flash = ModelConfig(provider=PROVIDER_OPENROUTER, model_id="google/gemini-2.5-flash")
    grok_fast = ModelConfig(provider=PROVIDER_OPENROUTER, model_id="x-ai/grok-4-fast")
    # Native DeepSeek models (api.deepseek.com, requires DEEPSEEK_API_KEY)
    deepseek_native_chat = ModelConfig(provider=PROVIDER_DEEPSEEK, model_id="deepseek-chat")
    deepseek_native_reasoner = ModelConfig(provider=PROVIDER_DEEPSEEK, model_id="deepseek-reasoner")
