"""Tests for the AdminServer aiohttp middleware."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer


def _stub_db_modules() -> None:
    """Inject stub db modules so AdminServer can be imported without sqlalchemy."""
    if "db.engine" not in sys.modules:
        engine_mod = ModuleType("db.engine")
        engine_mod.get_db = MagicMock()  # type: ignore[attr-defined]
        sys.modules["db.engine"] = engine_mod

    if "db.repository" not in sys.modules:
        repo_mod = ModuleType("db.repository")
        repo_mod.GameRepository = MagicMock()  # type: ignore[attr-defined]
        sys.modules["db.repository"] = repo_mod


_stub_db_modules()

from interfaces.admin import AdminServer  # noqa: E402  (must be after stubs)


def _make_app(token: str | None = None) -> web.Application:
    return AdminServer(MagicMock(), port=0, token=token)._app


@pytest.fixture
def app_no_token() -> web.Application:
    return _make_app(token=None)


@pytest.fixture
def app_with_token() -> web.Application:
    return _make_app(token="secret")


@pytest.mark.asyncio
async def test_middleware_no_token_allows_api(app_no_token: web.Application) -> None:
    """Without a token configured, all API requests pass through."""
    async with TestClient(TestServer(app_no_token)) as client:
        mock_repo = AsyncMock()
        mock_repo.list_sessions.return_value = []
        with (
            patch("interfaces.admin.get_db") as mock_get_db,
            patch("interfaces.admin.GameRepository", return_value=mock_repo),
        ):
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
            resp = await client.get("/api/sessions")
            assert resp.status == 200


@pytest.mark.asyncio
async def test_middleware_with_token_rejects_missing_auth(app_with_token: web.Application) -> None:
    """With a token configured, requests without Authorization header get 401."""
    async with TestClient(TestServer(app_with_token)) as client:
        resp = await client.get("/api/sessions")
        assert resp.status == 401
        resp_body = await resp.json()
        assert resp_body == {"error": "Unauthorized"}


@pytest.mark.asyncio
async def test_middleware_with_token_rejects_wrong_token(app_with_token: web.Application) -> None:
    """Wrong token yields 401."""
    async with TestClient(TestServer(app_with_token)) as client:
        resp = await client.get("/api/sessions", headers={"Authorization": "Bearer wrong"})
        assert resp.status == 401


@pytest.mark.asyncio
async def test_middleware_with_token_allows_correct_token(app_with_token: web.Application) -> None:
    """Correct Bearer token allows the request through."""
    async with TestClient(TestServer(app_with_token)) as client:
        mock_repo = AsyncMock()
        mock_repo.list_sessions.return_value = []
        with (
            patch("interfaces.admin.get_db") as mock_get_db,
            patch("interfaces.admin.GameRepository", return_value=mock_repo),
        ):
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
            resp = await client.get("/api/sessions", headers={"Authorization": "Bearer secret"})
            assert resp.status == 200


@pytest.mark.asyncio
async def test_middleware_does_not_block_dashboard(app_with_token: web.Application) -> None:
    """Non-/api/ routes are not subject to token check."""
    async with TestClient(TestServer(app_with_token)) as client:
        resp = await client.get("/")
        assert resp.status in {200, 404}
