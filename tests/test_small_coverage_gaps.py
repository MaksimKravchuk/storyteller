"""Focused tests to cover small remaining gaps across config, prompts, filters, helpers."""

from __future__ import annotations

import json
from datetime import datetime

import allure
import pytest

from config import Config, get_api_key_for_provider, load_config
from interfaces.admin_route_helpers import _json_response, _json_serial
from knowledge.node import KnowledgeNode, KnowledgeScope
from knowledge.query_filters import passes_location
from prompts.base_template import PromptSection, PromptTemplate


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Defaults & model config")
class TestLoadConfig:
    @allure.story("Environment loading")
    @allure.title("load_config reads OPENAI_API_KEY and model overrides from the environment")
    def test_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anthro-test")
        monkeypatch.setenv("DIRECTOR_MODEL", "gpt-custom")
        monkeypatch.setenv("AGENT_MODEL", "gpt-mini")
        monkeypatch.setenv("NARRATOR_MODEL", "gpt-narr")
        monkeypatch.setenv("DEFAULT_PROVIDER", "local")
        monkeypatch.setenv("TEMPERATURE", "0.2")
        monkeypatch.setenv("MAX_TOKENS", "512")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-token")

        cfg = load_config()

        assert cfg.openai_api_key == "sk-test"
        assert cfg.anthropic_api_key == "anthro-test"
        assert cfg.director_model == "gpt-custom"
        assert cfg.agent_model == "gpt-mini"
        assert cfg.narrator_model == "gpt-narr"
        assert cfg.default_provider == "local"
        assert cfg.temperature == pytest.approx(0.2)
        assert cfg.max_tokens == 512
        assert cfg.telegram_bot_token == "tg-token"


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Defaults & model config")
class TestApiKeyForProvider:
    @allure.story("API key routing")
    @allure.title("get_api_key_for_provider returns the openai key for the openai provider")
    def test_openai(self):
        cfg = Config(openai_api_key="sk-o", anthropic_api_key="sk-a")
        assert get_api_key_for_provider("openai", cfg) == "sk-o"

    @allure.story("API key routing")
    @allure.title("get_api_key_for_provider returns the anthropic key for the anthropic provider")
    def test_anthropic(self):
        cfg = Config(openai_api_key="sk-o", anthropic_api_key="sk-a")
        assert get_api_key_for_provider("anthropic", cfg) == "sk-a"

    @allure.story("API key routing")
    @allure.title("get_api_key_for_provider returns None for any unknown provider")
    def test_unknown_returns_none(self):
        cfg = Config(openai_api_key="sk-o")
        assert get_api_key_for_provider("local", cfg) is None


@allure.epic("Scene & Exploration")
@allure.feature("Knowledge graph")
class TestPassesLocation:
    @allure.story("Query filtering")
    @allure.title("passes_location rejects a LOCAL node whose location_id does not match the query")
    def test_local_node_rejected_when_location_mismatches(self):
        node = KnowledgeNode(
            text="A local gossip",
            scope=KnowledgeScope.LOCAL,
            location_id="tavern",
        )
        assert passes_location(node, "market") is False

    @allure.story("Query filtering")
    @allure.title("passes_location accepts a LOCAL node whose location_id matches the query")
    def test_local_node_accepted_when_location_matches(self):
        node = KnowledgeNode(
            text="A local gossip",
            scope=KnowledgeScope.LOCAL,
            location_id="tavern",
        )
        assert passes_location(node, "tavern") is True


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Prompt templating")
class TestPromptTemplateBuilder:
    @allure.story("Section building")
    @allure.title("PromptSection.render raises ValueError when required vars are missing")
    def test_section_missing_required_var_raises(self):
        section = PromptSection(name="S", template="{name}", required_vars=["name"])

        with pytest.raises(ValueError, match="Missing template variables"):
            section.render()

    @allure.story("Section building")
    @allure.title("PromptTemplate renders all sections whose required vars are satisfied")
    def test_template_renders_satisfied_sections(self):
        section = PromptSection(name="greeting", template="Hello, {name}!", required_vars=["name"])
        template = PromptTemplate([section])

        assert template.render(name="world") == "Hello, world!"


@allure.epic("Player Interfaces")
@allure.feature("Admin dashboard")
class TestAdminJsonSerial:
    @allure.story("JSON serialisation")
    @allure.title("_json_serial converts datetime objects to ISO-8601 strings")
    def test_datetime_serialises_to_isoformat(self):
        moment = datetime(2026, 4, 11, 12, 30, 0)
        assert _json_serial(moment) == moment.isoformat()

    @allure.story("JSON serialisation")
    @allure.title("_json_serial raises TypeError for objects it does not know how to serialise")
    def test_unknown_type_raises(self):
        with pytest.raises(TypeError, match="not serializable"):
            _json_serial(object())

    @allure.story("JSON serialisation")
    @allure.title("_json_response round-trips datetime values through the custom serializer")
    def test_json_response_serialises_datetime(self):
        moment = datetime(2026, 4, 11, 12, 30, 0)
        resp = _json_response({"when": moment})

        payload = json.loads(resp.text)
        assert payload == {"when": moment.isoformat()}
