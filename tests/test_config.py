"""Tests for config module and defaults package exports."""

from __future__ import annotations

import allure

from config import Config, get_api_key_for_provider, list_api_key_status, resolve_model_config
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
        cfg = resolve_model_config(_GPT5_4_MINI, Config())
        assert cfg.provider == _OPENAI
        assert cfg.model_id == _GPT5_4_MINI

    @allure.story("Provider auto-detection")
    @allure.title("resolve_model_config routes any claude-* model id to the anthropic provider")
    def test_claude_model_resolves_to_anthropic(self):
        cfg = resolve_model_config("claude-sonnet-4-20250514", Config())
        assert cfg.provider == "anthropic"

    @allure.story("Provider auto-detection")
    @allure.title("resolve_model_config falls back to the configured default_provider for unknown model ids")
    def test_unknown_model_uses_default_provider(self):
        cfg = resolve_model_config("llama-3", Config(default_provider="local"))
        assert cfg.provider == "local"


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("OpenRouter provider")
class TestOpenRouterDetection:
    @allure.story("Provider auto-detection")
    @allure.title("Model ids with OpenRouter-family prefixes resolve to the openrouter provider")
    def test_openrouter_prefixes_resolve_to_openrouter(self):
        openrouter_samples = [
            "deepseek/deepseek-chat-v3.1",
            "google/gemini-2.5-pro",
            "x-ai/grok-4-fast",
            "qwen/qwen-plus",
            "moonshotai/kimi-k2",
            "meta-llama/llama-3.3-70b-instruct",
            "mistralai/mistral-large",
        ]
        cfg = Config()
        for model_id in openrouter_samples:
            resolved = resolve_model_config(model_id, cfg)
            assert resolved.provider == "openrouter", model_id
            assert resolved.model_id == model_id

    @allure.story("API-key status")
    @allure.title("list_api_key_status reports all four providers based on Config values")
    def test_list_api_key_status_reflects_config(self):
        cfg = Config(
            openai_api_key="sk-a",
            anthropic_api_key=None,
            openrouter_api_key="or-b",
            deepseek_api_key=None,
        )
        status = list_api_key_status(cfg)
        assert status == {
            "openai": True,
            "anthropic": False,
            "openrouter": True,
            "deepseek": False,
        }

    @allure.story("API-key status")
    @allure.title("get_api_key_for_provider returns the OpenRouter key when requested")
    def test_get_api_key_returns_openrouter(self):
        cfg = Config(openrouter_api_key="or-key-123")
        assert get_api_key_for_provider("openrouter", cfg) == "or-key-123"

    @allure.story("API-key status")
    @allure.title("get_api_key_for_provider returns None for unknown providers")
    def test_get_api_key_unknown_provider_returns_none(self):
        assert get_api_key_for_provider("cohere", Config()) is None


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("DeepSeek provider")
class TestDeepSeekDetection:
    @allure.story("Provider auto-detection")
    @allure.title("Bare deepseek-* model ids resolve to the native deepseek provider")
    def test_native_deepseek_prefix_resolves_to_deepseek(self):
        cfg = Config()
        for model_id in ("deepseek-chat", "deepseek-reasoner"):
            resolved = resolve_model_config(model_id, cfg)
            assert resolved.provider == "deepseek", model_id
            assert resolved.model_id == model_id

    @allure.story("Provider auto-detection")
    @allure.title("Slash-prefixed deepseek/<model> ids stay routed through OpenRouter")
    def test_slash_prefixed_deepseek_stays_openrouter(self):
        resolved = resolve_model_config("deepseek/deepseek-chat-v3.1", Config())
        assert resolved.provider == "openrouter"

    @allure.story("API-key status")
    @allure.title("get_api_key_for_provider returns the DeepSeek key when requested")
    def test_get_api_key_returns_deepseek(self):
        cfg = Config(deepseek_api_key="ds-key-123")
        assert get_api_key_for_provider("deepseek", cfg) == "ds-key-123"
