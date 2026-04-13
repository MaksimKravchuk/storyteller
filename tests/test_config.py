"""Tests for config module and defaults package exports."""

from __future__ import annotations

import allure

from defaults.models import AI_MODELS, ModelConfig

_OPENAI = "openai"
_GPT5_4_MINI = "gpt-5.4-mini"
_GPT5_4_NANO = "gpt-5.4-nano"


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Defaults & model config")
class TestDefaultsExports:
    @allure.story("AI_MODELS registry")
    @allure.title("The ModelConfig dataclass is importable from defaults.models")
    def test_modelconfig_importable(self):
        assert ModelConfig is not None

    @allure.story("AI_MODELS registry")
    @allure.title("The AI_MODELS registry is importable from defaults.models")
    def test_ai_models_importable(self):
        assert AI_MODELS is not None

    @allure.story("ModelConfig dataclass")
    @allure.title("ModelConfig constructs with explicit provider and model_id and exposes them as attributes")
    def test_modelconfig_is_dataclass(self):
        cfg = ModelConfig(provider=_OPENAI, model_id=_GPT5_4_MINI)
        assert cfg.provider == _OPENAI
        assert cfg.model_id == _GPT5_4_MINI

    @allure.story("AI_MODELS registry")
    @allure.title("AI_MODELS.gpt5_4_mini is preconfigured as the OpenAI gpt-5.4-mini model")
    def test_ai_models_gpt5_4_mini(self):
        assert AI_MODELS.gpt5_4_mini.provider == _OPENAI
        assert AI_MODELS.gpt5_4_mini.model_id == _GPT5_4_MINI

    @allure.story("AI_MODELS registry")
    @allure.title("AI_MODELS.gpt5_4_nano is preconfigured as the OpenAI gpt-5.4-nano model")
    def test_ai_models_gpt5_4_nano(self):
        assert AI_MODELS.gpt5_4_nano.provider == _OPENAI
        assert AI_MODELS.gpt5_4_nano.model_id == _GPT5_4_NANO


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Defaults & model config")
class TestResolveModelConfig:
    @allure.story("Provider auto-detection")
    @allure.title("resolve_model_config routes any gpt-* model id to the openai provider")
    def test_gpt_model_resolves_to_openai(self):
        from config import Config, resolve_model_config

        cfg = resolve_model_config(_GPT5_4_MINI, Config())
        assert cfg.provider == _OPENAI
        assert cfg.model_id == _GPT5_4_MINI

    @allure.story("Provider auto-detection")
    @allure.title("resolve_model_config routes any claude-* model id to the anthropic provider")
    def test_claude_model_resolves_to_anthropic(self):
        from config import Config, resolve_model_config

        cfg = resolve_model_config("claude-sonnet-4-20250514", Config())
        assert cfg.provider == "anthropic"

    @allure.story("Provider auto-detection")
    @allure.title("resolve_model_config falls back to the configured default_provider for unknown model ids")
    def test_unknown_model_uses_default_provider(self):
        from config import Config, resolve_model_config

        cfg = resolve_model_config("llama-3", Config(default_provider="local"))
        assert cfg.provider == "local"
