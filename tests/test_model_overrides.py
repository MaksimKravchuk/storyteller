"""Tests for engine.model_overrides — bridge between DB overrides and ModelConfig."""

from __future__ import annotations

from unittest.mock import AsyncMock

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


@allure.story("load_role_overrides")
@allure.title("Empty DB produces an empty override mapping")
@pytest.mark.asyncio
async def test_empty_returns_empty() -> None:
    result = await load_role_overrides(_make_repo({}))
    assert result == {}


@allure.story("load_role_overrides")
@allure.title("DB rows are wrapped into ModelConfig objects with provider and model_id")
@pytest.mark.asyncio
async def test_wraps_rows_into_model_configs() -> None:
    repo = _make_repo(
        {
            "narrator": ("anthropic", "claude-opus-4-6"),
            "director": ("openrouter", "deepseek/deepseek-chat-v3.1"),
        }
    )

    result = await load_role_overrides(repo)

    assert result["narrator"].provider == "anthropic"
    assert result["narrator"].model_id == "claude-opus-4-6"
    assert result["director"].provider == "openrouter"
    assert result["director"].model_id == "deepseek/deepseek-chat-v3.1"
