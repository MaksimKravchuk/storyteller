"""Tests for AdminSettingsStore — per-role model overrides."""

from __future__ import annotations

import allure
import pytest

pytestmark = [
    pytest.mark.db,
    allure.epic("Admin panel"),
    allure.feature("Model overrides"),
]


@allure.story("Empty store")
@allure.title("get_model_overrides returns empty dict when table is empty")
@pytest.mark.asyncio
async def test_empty_returns_empty_dict(repo) -> None:
    result = await repo.settings.get_model_overrides()
    assert result == {}


@allure.story("Upsert")
@allure.title("set_model inserts a new row and get_model_overrides reads it back")
@pytest.mark.asyncio
async def test_set_model_inserts_and_reads_back(repo) -> None:
    await repo.settings.set_model("narrator", "anthropic", "claude-opus-4-6")

    result = await repo.settings.get_model_overrides()
    assert result == {"narrator": ("anthropic", "claude-opus-4-6")}


@allure.story("Upsert")
@allure.title("set_model updates an existing row in place (idempotent per role)")
@pytest.mark.asyncio
async def test_set_model_updates_existing(repo) -> None:
    await repo.settings.set_model("narrator", "openai", "gpt-5.4-mini")
    await repo.settings.set_model("narrator", "anthropic", "claude-sonnet-4-20250514")

    result = await repo.settings.get_model_overrides()
    assert result == {"narrator": ("anthropic", "claude-sonnet-4-20250514")}


@allure.story("Upsert")
@allure.title("set_model stores OpenRouter-routed model ids round-trip")
@pytest.mark.asyncio
async def test_set_model_roundtrip_openrouter(repo) -> None:
    await repo.settings.set_model("director", "openrouter", "deepseek/deepseek-chat-v3.1")

    result = await repo.settings.get_model_overrides()
    assert result == {"director": ("openrouter", "deepseek/deepseek-chat-v3.1")}


@allure.story("Validation")
@allure.title("set_model rejects unknown role with ValueError")
@pytest.mark.asyncio
async def test_set_model_rejects_unknown_role(repo) -> None:
    with pytest.raises(ValueError, match="unknown role"):
        await repo.settings.set_model("mastermind", "openai", "gpt-5.4")


@allure.story("Validation")
@allure.title("set_model rejects unknown provider with ValueError")
@pytest.mark.asyncio
async def test_set_model_rejects_unknown_provider(repo) -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        await repo.settings.set_model("narrator", "cohere", "command-r")


@allure.story("Validation")
@allure.title("set_model rejects empty model_id with ValueError")
@pytest.mark.asyncio
async def test_set_model_rejects_empty_model_id(repo) -> None:
    with pytest.raises(ValueError, match="model_id"):
        await repo.settings.set_model("narrator", "openai", "")


@allure.story("Upsert")
@allure.title("Multiple roles coexist independently in the store")
@pytest.mark.asyncio
async def test_multiple_roles_coexist(repo) -> None:
    await repo.settings.set_model("director", "openai", "gpt-5.4-mini")
    await repo.settings.set_model("narrator", "anthropic", "claude-opus-4-6")
    await repo.settings.set_model("agent", "openrouter", "deepseek/deepseek-chat-v3.1")

    result = await repo.settings.get_model_overrides()
    assert result == {
        "director": ("openai", "gpt-5.4-mini"),
        "narrator": ("anthropic", "claude-opus-4-6"),
        "agent": ("openrouter", "deepseek/deepseek-chat-v3.1"),
    }
