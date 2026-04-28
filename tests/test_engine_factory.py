"""Tests for engine.factory — create_engine and create_engine_from_state."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from defaults.models import AI_MODELS, ModelConfig
from engine.factory import create_engine, create_engine_from_state, create_engine_with_db_overrides
from engine.game_engine import GameEngine
from knowledge.graph import KnowledgeGraph

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Engine factory"),
]


def _make_config() -> MagicMock:
    cfg = MagicMock()
    cfg.director_model = "gpt-5.4-mini"
    cfg.agent_model = "gpt-5.4-nano"
    cfg.narrator_model = "gpt-5.4-mini"
    cfg.dramaturge_model = "gpt-5.4-nano"
    cfg.dramaturge_enabled = False
    cfg.openai_api_key = "openai-key"
    cfg.anthropic_api_key = "anthropic-key"
    cfg.openrouter_api_key = "openrouter-key"
    cfg.deepseek_api_key = "deepseek-key"
    return cfg


def _resolver_side_effect(model_id: str, _cfg) -> ModelConfig:
    if model_id == "gpt-5.4-nano":
        return AI_MODELS.gpt5_4_nano
    return AI_MODELS.gpt5_4_mini


@allure.story("create_engine")
@allure.title("create_engine builds a GameEngine with api_keys and language from the supplied Config")
def test_create_engine_returns_game_engine_with_defaults() -> None:
    """create_engine must return a GameEngine wired with config-derived models and keys."""
    cfg = _make_config()
    with patch("engine.factory.resolve_model_config", side_effect=_resolver_side_effect):
        engine = create_engine(cfg)

    assert isinstance(engine, GameEngine)
    # Private attrs are part of this test's contract since factory is a narrow wrapper.
    assert engine._language == "English"
    assert engine._api_keys == {
        "openai": "openai-key",
        "anthropic": "anthropic-key",
        "openrouter": "openrouter-key",
        "deepseek": "deepseek-key",
    }
    assert engine._models.director is AI_MODELS.gpt5_4_mini
    assert engine._models.agent is AI_MODELS.gpt5_4_nano
    assert engine._models.narrator is AI_MODELS.gpt5_4_mini
    # Dramaturge is off by default — no model should be resolved for it.
    assert engine._models.dramaturge is None


@allure.story("create_engine")
@allure.title("create_engine forwards a non-English language argument to the GameEngine")
def test_create_engine_propagates_language() -> None:
    """language kwarg must be forwarded into GameEngine."""
    cfg = _make_config()
    with patch("engine.factory.resolve_model_config", side_effect=_resolver_side_effect):
        engine = create_engine(cfg, language="Russian")
    assert engine._language == "Russian"


@allure.story("create_engine")
@allure.title("create_engine calls resolve_model_config three times for director, agent, and narrator models")
def test_create_engine_resolves_three_model_ids() -> None:
    """resolve_model_config must be invoked once per role when the dramaturge flag is off."""
    cfg = _make_config()
    with patch(
        "engine.factory.resolve_model_config",
        side_effect=_resolver_side_effect,
    ) as resolver:
        create_engine(cfg)
        assert resolver.call_count == 3
        called_ids = [call.args[0] for call in resolver.call_args_list]
        assert called_ids == ["gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.4-mini"]


@allure.story("create_engine")
@allure.title("create_engine resolves a dramaturge model when dramaturge_enabled is true")
def test_create_engine_resolves_dramaturge_model_when_enabled() -> None:
    """When the feature flag is on, the dramaturge model is resolved alongside the core three."""
    cfg = _make_config()
    cfg.dramaturge_enabled = True
    with patch(
        "engine.factory.resolve_model_config",
        side_effect=_resolver_side_effect,
    ) as resolver:
        engine = create_engine(cfg)
        assert resolver.call_count == 4
        called_ids = [call.args[0] for call in resolver.call_args_list]
        assert called_ids == ["gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.4-mini", "gpt-5.4-nano"]
    assert engine._models.dramaturge is AI_MODELS.gpt5_4_nano


@allure.story("create_engine_from_state")
@allure.title("create_engine_from_state builds an engine and awaits its restore_session with saved state")
@pytest.mark.asyncio
async def test_create_engine_from_state_calls_restore(simple_setting) -> None:
    """create_engine_from_state must call engine.restore_session once with the saved state args."""
    cfg = _make_config()
    graph = KnowledgeGraph()
    from models.game_state import GameState

    saved_state = GameState(setting=simple_setting, knowledge_graph=graph)

    restore_mock = AsyncMock()
    with (
        patch("engine.factory.resolve_model_config", side_effect=_resolver_side_effect),
        patch.object(GameEngine, "restore_session", restore_mock),
    ):
        engine = await create_engine_from_state(cfg, saved_state, graph, [])

    assert isinstance(engine, GameEngine)
    restore_mock.assert_awaited_once_with(saved_state, graph, [])


@allure.story("create_engine")
@allure.title("create_engine applies DB overrides and skips resolve_model_config for overridden roles")
def test_create_engine_applies_overrides() -> None:
    """When overrides are supplied, overridden roles bypass resolve_model_config."""
    cfg = _make_config()
    overrides = {
        "narrator": AI_MODELS.claude_sonnet,
        "director": AI_MODELS.claude_opus,
    }
    with patch(
        "engine.factory.resolve_model_config",
        side_effect=_resolver_side_effect,
    ) as resolver:
        engine = create_engine(cfg, overrides=overrides)

    # Overridden roles come from the override dict directly.
    assert engine._models.director is AI_MODELS.claude_opus
    assert engine._models.narrator is AI_MODELS.claude_sonnet
    # Unoverridden role still uses the resolver.
    assert engine._models.agent is AI_MODELS.gpt5_4_nano
    # Only the agent role called resolve_model_config.
    assert resolver.call_count == 1
    assert resolver.call_args_list[0].args[0] == "gpt-5.4-nano"


@allure.story("create_engine_with_db_overrides")
@allure.title("create_engine_with_db_overrides reads DB overrides and applies them to the built engine")
@pytest.mark.asyncio
async def test_create_engine_with_db_overrides_reads_repo_and_applies() -> None:
    """The convenience wrapper must read role overrides from the repo and apply them."""
    cfg = _make_config()
    repo = AsyncMock()
    repo.settings.get_model_overrides.return_value = {
        "narrator": ("anthropic", "claude-opus-4-6"),
    }
    with patch("engine.factory.resolve_model_config", side_effect=_resolver_side_effect):
        engine = await create_engine_with_db_overrides(repo, cfg, language="Russian")

    repo.settings.get_model_overrides.assert_awaited_once()
    assert engine._language == "Russian"
    assert engine._models.narrator.provider == "anthropic"
    assert engine._models.narrator.model_id == "claude-opus-4-6"
    # Non-overridden roles still come from the env defaults.
    assert engine._models.director is AI_MODELS.gpt5_4_mini


@allure.story("create_engine_from_state")
@allure.title("create_engine_from_state ignores the overrides pathway — restored games keep originals")
@pytest.mark.asyncio
async def test_create_engine_from_state_does_not_apply_overrides(simple_setting) -> None:
    """Restore path must resolve from env only, never from overrides."""
    cfg = _make_config()
    graph = KnowledgeGraph()
    from models.game_state import GameState

    saved_state = GameState(setting=simple_setting, knowledge_graph=graph)

    restore_mock = AsyncMock()
    with (
        patch(
            "engine.factory.resolve_model_config",
            side_effect=_resolver_side_effect,
        ) as resolver,
        patch.object(GameEngine, "restore_session", restore_mock),
    ):
        engine = await create_engine_from_state(cfg, saved_state, graph, [])

    # Resolver called for every role (no overrides applied).
    assert resolver.call_count == 3
    assert engine._models.director is AI_MODELS.gpt5_4_mini
    assert engine._models.narrator is AI_MODELS.gpt5_4_mini
