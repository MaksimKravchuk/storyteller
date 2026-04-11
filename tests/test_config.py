"""Tests for config module and defaults package exports."""

from __future__ import annotations

import allure

from defaults.models import AI_MODELS, ModelConfig

_OPENAI = "openai"
_GPT4 = "gpt-4"
_GPT35_TURBO = "gpt-3.5-turbo"


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
        cfg = ModelConfig(provider=_OPENAI, model_id=_GPT4)
        assert cfg.provider == _OPENAI
        assert cfg.model_id == _GPT4

    @allure.story("AI_MODELS registry")
    @allure.title("AI_MODELS.gpt4 is preconfigured as the OpenAI gpt-4 model")
    def test_ai_models_gpt4(self):
        assert AI_MODELS.gpt4.provider == _OPENAI
        assert AI_MODELS.gpt4.model_id == _GPT4

    @allure.story("AI_MODELS registry")
    @allure.title("AI_MODELS.gpt35_turbo is preconfigured as the OpenAI gpt-3.5-turbo model")
    def test_ai_models_gpt35_turbo(self):
        assert AI_MODELS.gpt35_turbo.provider == _OPENAI
        assert AI_MODELS.gpt35_turbo.model_id == _GPT35_TURBO


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Defaults & model config")
class TestResolveModelConfig:
    @allure.story("Provider auto-detection")
    @allure.title("resolve_model_config routes any gpt-* model id to the openai provider")
    def test_gpt_model_resolves_to_openai(self):
        from config import Config, resolve_model_config

        cfg = resolve_model_config(_GPT4, Config())
        assert cfg.provider == _OPENAI
        assert cfg.model_id == _GPT4

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
