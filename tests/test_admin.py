"""Tests for the AdminServer aiohttp middleware — no-auth and dashboard tests."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

_API_SESSIONS = "/api/sessions"
_HTTP_OK = 200
_HTTP_UNAUTHORIZED = 401


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

from interfaces.admin import AdminServer  # noqa: E402


def _make_app(token=None) -> web.Application:
    return AdminServer(MagicMock(), port=0, token=token)._app


@pytest.mark.asyncio
async def test_middleware_no_token_allows_api() -> None:
    """Without a token configured, all API requests pass through."""
    async with TestClient(TestServer(_make_app())) as client:
        mock_repo = AsyncMock()
        mock_repo.admin.list_sessions.return_value = []
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
            resp = await client.get(_API_SESSIONS)
            assert resp.status == _HTTP_OK


@pytest.mark.asyncio
async def test_middleware_does_not_block_dashboard() -> None:
    """Non-/api/ routes are not subject to token check."""
    async with TestClient(TestServer(_make_app(token="secret"))) as client:
        resp = await client.get("/")
        assert resp.status not in {_HTTP_UNAUTHORIZED, 403}
