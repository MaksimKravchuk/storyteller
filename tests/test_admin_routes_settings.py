"""Coverage for interfaces.admin_routes_settings — keys / models / set_model endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from fastapi import FastAPI

from tests.admin_app import admin_client, make_admin_app

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin settings routes"),
]

_HTTP_OK = 200
_HTTP_BAD_REQUEST = 400
_HTTP_CONFLICT = 409
_API_KEYS = "/api/settings/keys"
_API_MODELS = "/api/settings/models"


def _make_app_with_cfg(cfg: MagicMock) -> FastAPI:
    """Build an admin app bound to a specific Config mock."""
    return make_admin_app(cfg)


def _make_cfg(
    openai: str | None = "sk-o",
    anthropic: str | None = "sk-a",
    openrouter: str | None = "sk-r",
    deepseek: str | None = "sk-d",
) -> MagicMock:
    cfg = MagicMock()
    cfg.openai_api_key = openai
    cfg.anthropic_api_key = anthropic
    cfg.openrouter_api_key = openrouter
    cfg.deepseek_api_key = deepseek
    cfg.director_model = "gpt-5.4-mini"
    cfg.agent_model = "gpt-5.4-nano"
    cfg.narrator_model = "gpt-5.4-mini"
    cfg.dramaturge_model = "gpt-5.4-nano"
    return cfg


def _prime_get_db(mock_get_db) -> None:
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)


@allure.story("API key status")
@allure.title("GET /api/settings/keys reports per-provider configured/missing booleans")
@pytest.mark.asyncio
async def test_keys_route_reports_booleans() -> None:
    cfg = _make_cfg(openai="sk-o", anthropic=None, openrouter="or-key", deepseek=None)
    async with admin_client(_make_app_with_cfg(cfg)) as client:
        resp = await client.get(_API_KEYS)
        status = resp.status_code
        body = resp.json()
    assert status == _HTTP_OK
    assert body == {
        "openai": True,
        "anthropic": False,
        "openrouter": True,
        "deepseek": False,
    }


@allure.story("Model overrides")
@allure.title("GET /api/settings/models returns env source when no DB override exists")
@pytest.mark.asyncio
async def test_get_models_env_fallback() -> None:
    cfg = _make_cfg()
    mock_repo = AsyncMock()
    mock_repo.settings.get_model_overrides.return_value = {}

    async with admin_client(_make_app_with_cfg(cfg)) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get(_API_MODELS)
            body = resp.json()

    for role in ("director", "agent", "narrator", "dramaturge"):
        assert body["roles"][role]["source"] == "env"
    assert body["roles"]["director"]["model_id"] == "gpt-5.4-mini"
    assert body["roles"]["director"]["provider"] == "openai"
    # catalog is present and non-empty
    assert any(entry["provider"] == "openrouter" for entry in body["catalog"])


@allure.story("Model overrides")
@allure.title("GET /api/settings/models reports DB source when an override row exists")
@pytest.mark.asyncio
async def test_get_models_db_override() -> None:
    cfg = _make_cfg()
    mock_repo = AsyncMock()
    mock_repo.settings.get_model_overrides.return_value = {
        "narrator": ("anthropic", "claude-opus-4-6"),
    }

    async with admin_client(_make_app_with_cfg(cfg)) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get(_API_MODELS)
            body = resp.json()

    assert body["roles"]["narrator"] == {
        "provider": "anthropic",
        "model_id": "claude-opus-4-6",
        "source": "db",
    }
    assert body["roles"]["director"]["source"] == "env"


async def _post_set(cfg: MagicMock, mock_repo: AsyncMock, payload) -> tuple[int, dict]:
    async with admin_client(_make_app_with_cfg(cfg)) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.post(_API_MODELS, json=payload)
            return resp.status_code, resp.json()


@allure.story("Model overrides")
@allure.title("POST /api/settings/models persists a valid override and echoes the payload")
@pytest.mark.asyncio
async def test_post_set_model_happy_path() -> None:
    cfg = _make_cfg()
    mock_repo = AsyncMock()
    payload = {"role": "narrator", "provider": "anthropic", "model_id": "claude-opus-4-6"}

    status, body = await _post_set(cfg, mock_repo, payload)

    assert status == _HTTP_OK
    assert body["ok"] is True
    mock_repo.settings.set_model.assert_awaited_once_with(
        "narrator",
        "anthropic",
        "claude-opus-4-6",
    )


@allure.story("Model overrides")
@allure.title("POST rejects an unknown role with 400")
@pytest.mark.asyncio
async def test_post_set_model_unknown_role() -> None:
    cfg = _make_cfg()
    mock_repo = AsyncMock()
    status, _ = await _post_set(cfg, mock_repo, {"role": "wizard", "provider": "openai", "model_id": "gpt"})
    assert status == _HTTP_BAD_REQUEST
    mock_repo.settings.set_model.assert_not_awaited()


@allure.story("Model overrides")
@allure.title("POST rejects an unknown provider with 400")
@pytest.mark.asyncio
async def test_post_set_model_unknown_provider() -> None:
    cfg = _make_cfg()
    mock_repo = AsyncMock()
    status, _ = await _post_set(cfg, mock_repo, {"role": "narrator", "provider": "cohere", "model_id": "cmd"})
    assert status == _HTTP_BAD_REQUEST
    mock_repo.settings.set_model.assert_not_awaited()


@allure.story("Model overrides")
@allure.title("POST rejects an empty model_id with 400")
@pytest.mark.asyncio
async def test_post_set_model_empty_model_id() -> None:
    cfg = _make_cfg()
    mock_repo = AsyncMock()
    status, _ = await _post_set(cfg, mock_repo, {"role": "narrator", "provider": "openai", "model_id": "   "})
    assert status == _HTTP_BAD_REQUEST


@allure.story("Model overrides")
@allure.title("POST returns 409 when the chosen provider has no API key configured")
@pytest.mark.asyncio
async def test_post_set_model_provider_key_missing() -> None:
    cfg = _make_cfg(openrouter=None)
    mock_repo = AsyncMock()
    payload = {"role": "director", "provider": "openrouter", "model_id": "deepseek/deepseek-chat-v3.1"}

    status, body = await _post_set(cfg, mock_repo, payload)

    assert status == _HTTP_CONFLICT
    assert "openrouter" in body["error"]
    mock_repo.settings.set_model.assert_not_awaited()


@allure.story("Model overrides")
@allure.title("POST returns 400 when the body is not valid JSON")
@pytest.mark.asyncio
async def test_post_set_model_invalid_json() -> None:
    cfg = _make_cfg()
    async with admin_client(_make_app_with_cfg(cfg)) as client:
        resp = await client.post(_API_MODELS, content="not-json")
        status = resp.status_code
    assert status == _HTTP_BAD_REQUEST


@allure.story("Model overrides")
@allure.title("POST surfaces a repo-level ValueError as a 400 response")
@pytest.mark.asyncio
async def test_post_set_model_repo_value_error_becomes_400() -> None:
    cfg = _make_cfg()
    mock_repo = AsyncMock()
    mock_repo.settings.set_model.side_effect = ValueError("model_id must be 1..200 chars")
    payload = {"role": "narrator", "provider": "anthropic", "model_id": "claude-opus-4-6"}

    status, body = await _post_set(cfg, mock_repo, payload)

    assert status == _HTTP_BAD_REQUEST
    assert "model_id" in body["error"]
