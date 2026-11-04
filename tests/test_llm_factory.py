"""Tests for llm.factory.create_llm_client — provider routing and parameter forwarding."""

from __future__ import annotations

import asyncio

import allure
import pytest

from defaults.models import ModelConfig
from llm.anthropic_client import AnthropicClient
from llm.factory import _cached_client, create_llm_client
from llm.openai_client import OpenAIClient

_DUMMY_KEY = "dummy"


async def _build_in_loop(config: ModelConfig) -> object:
    return create_llm_client(config, _DUMMY_KEY)


@pytest.fixture(autouse=True)
def _fresh_client_cache() -> None:
    """The factory caches clients process-wide; isolate each test."""
    _cached_client.cache_clear()


@pytest.fixture
def _sdk_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure both SDKs find an API key so their constructors don't raise."""
    monkeypatch.setenv("OPENAI_API_KEY", _DUMMY_KEY)
    monkeypatch.setenv("ANTHROPIC_API_KEY", _DUMMY_KEY)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("LLM provider factory")
class TestCreateLLMClient:
    @allure.story("Provider routing")
    @allure.title("create_llm_client returns an OpenAIClient when the provider is openai")
    def test_openai_provider(self, _sdk_env: None) -> None:
        config = ModelConfig(provider="openai", model_id="gpt-4", temperature=0.25, max_tokens=512)
        client = create_llm_client(config)
        assert isinstance(client, OpenAIClient)
        assert client.model == "gpt-4"
        assert client.temperature == pytest.approx(0.25)
        assert client.max_tokens == 512

    @allure.story("Provider routing")
    @allure.title("create_llm_client returns an AnthropicClient when the provider is anthropic")
    def test_anthropic_provider(self, _sdk_env: None) -> None:
        config = ModelConfig(
            provider="anthropic",
            model_id="claude-sonnet-4-20250514",
            temperature=0.5,
            max_tokens=1024,
        )
        client = create_llm_client(config)
        assert isinstance(client, AnthropicClient)
        assert client.model == "claude-sonnet-4-20250514"
        assert client.temperature == pytest.approx(0.5)
        assert client.max_tokens == 1024

    @allure.story("Provider routing")
    @allure.title("create_llm_client raises ValueError when the provider is unknown")
    def test_unknown_provider(self, _sdk_env: None) -> None:
        config = ModelConfig(provider="bogus", model_id="x")
        with pytest.raises(ValueError, match="Unknown LLM provider: bogus"):
            create_llm_client(config)

    @allure.story("API key forwarding")
    @allure.title("create_llm_client forwards an explicit api_key to the OpenAI client")
    def test_openai_api_key_forwarded(self, _sdk_env: None) -> None:
        config = ModelConfig(provider="openai", model_id="gpt-4")
        client = create_llm_client(config, api_key="sk-custom")
        assert client.api_key == "sk-custom"

    @allure.story("API key forwarding")
    @allure.title("create_llm_client forwards an explicit api_key to the Anthropic client")
    def test_anthropic_api_key_forwarded(self, _sdk_env: None) -> None:
        config = ModelConfig(provider="anthropic", model_id="claude-sonnet-4-20250514")
        client = create_llm_client(config, api_key="ant-custom")
        assert client.api_key == "ant-custom"

    @allure.story("Default temperature")
    @allure.title("create_llm_client preserves the 0.7 default temperature when none is specified")
    def test_default_temperature(self, _sdk_env: None) -> None:
        config = ModelConfig(provider="openai", model_id="gpt-4")
        client = create_llm_client(config)
        assert client.temperature == pytest.approx(0.7)

    @allure.story("Provider routing")
    @allure.title("create_llm_client returns an OpenAIClient for openrouter provider with correct model and params")
    def test_openrouter_provider(self, _sdk_env: None) -> None:
        config = ModelConfig(
            provider="openrouter",
            model_id="deepseek/deepseek-chat-v3.1",
            temperature=0.4,
            max_tokens=1024,
        )
        client = create_llm_client(config, api_key="or-key")
        assert isinstance(client, OpenAIClient)
        assert client.model == "deepseek/deepseek-chat-v3.1"
        assert client.api_key == "or-key"
        assert client.temperature == pytest.approx(0.4)
        assert client.max_tokens == 1024

    @allure.story("Provider routing")
    @allure.title("create_llm_client returns an OpenAIClient for deepseek provider with correct model and params")
    def test_deepseek_provider(self, _sdk_env: None) -> None:
        config = ModelConfig(
            provider="deepseek",
            model_id="deepseek-chat",
            temperature=0.3,
            max_tokens=512,
        )
        client = create_llm_client(config, api_key="ds-key")
        assert isinstance(client, OpenAIClient)
        assert client.model == "deepseek-chat"
        assert client.api_key == "ds-key"
        assert client.temperature == pytest.approx(0.3)
        assert client.max_tokens == 512

    @allure.story("supports_structured_output")
    @allure.title("create_llm_client forwards supports_structured_output=False to AnthropicClient")
    def test_anthropic_supports_structured_output_forwarded(self, _sdk_env: None) -> None:
        config = ModelConfig(
            provider="anthropic",
            model_id="claude-sonnet-4-20250514",
            supports_structured_output=False,
        )
        client = create_llm_client(config)
        assert isinstance(client, AnthropicClient)
        assert client.supports_structured_output is False


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("LLM provider factory")
@allure.story("Client cache")
class TestClientCache:
    @allure.title("create_llm_client reuses one client per (config, api_key)")
    def test_same_key_returns_same_client(self, _sdk_env: None) -> None:
        config = ModelConfig(provider="openai", model_id="gpt-4")
        assert create_llm_client(config, "k1") is create_llm_client(config, "k1")

    @allure.title("create_llm_client builds separate clients for a different api_key or config")
    def test_different_key_or_config_returns_new_client(self, _sdk_env: None) -> None:
        config = ModelConfig(provider="openai", model_id="gpt-4")
        client = create_llm_client(config, "k1")
        assert create_llm_client(config, "k2") is not client
        assert create_llm_client(ModelConfig(provider="openai", model_id="gpt-4", temperature=0.1), "k1") is not client

    @allure.title("create_llm_client does not share a client across event loops")
    def test_different_event_loop_returns_new_client(self, _sdk_env: None) -> None:
        config = ModelConfig(provider="openai", model_id="gpt-4")
        assert asyncio.run(_build_in_loop(config)) is not asyncio.run(_build_in_loop(config))
