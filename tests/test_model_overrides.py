"""Tests for engine.model_overrides — bridge between DB overrides and ModelConfig."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from engine.model_overrides import load_role_overrides

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Model overrides"),
]


def _make_repo(overrides: dict) -> AsyncMock:
    repo = AsyncMock()
    repo.settings.get_model_overrides.return_value = overrides
    return repo


def _make_cfg() -> MagicMock:
    cfg = MagicMock()
    cfg.temperature = 0.55
    cfg.max_tokens = 1234
    return cfg


@allure.story("load_role_overrides")
@allure.title("Empty DB produces an empty override mapping")
@pytest.mark.asyncio
async def test_empty_returns_empty() -> None:
    result = await load_role_overrides(_make_repo({}), _make_cfg())
    assert result == {}


@allure.story("load_role_overrides")
@allure.title("DB rows are wrapped into ModelConfig objects with temperature & max_tokens from Config")
@pytest.mark.asyncio
async def test_wraps_rows_with_cfg_params() -> None:
    repo = _make_repo(
        {
            "narrator": ("anthropic", "claude-opus-4-6"),
            "director": ("openrouter", "deepseek/deepseek-chat-v3.1"),
        }
    )
    cfg = _make_cfg()

    result = await load_role_overrides(repo, cfg)

    assert result["narrator"].provider == "anthropic"
    assert result["narrator"].model_id == "claude-opus-4-6"
    assert result["narrator"].temperature == pytest.approx(0.55)
    assert result["narrator"].max_tokens == 1234
    assert result["director"].provider == "openrouter"
    assert result["director"].model_id == "deepseek/deepseek-chat-v3.1"
