"""Tests for llm.factory.create_llm_client — provider routing and parameter forwarding."""

from __future__ import annotations

import allure
import pytest

from defaults.models import ModelConfig
from llm.anthropic_client import AnthropicClient
from llm.factory import create_llm_client
from llm.openai_client import OpenAIClient

_DUMMY_KEY = "dummy"


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
