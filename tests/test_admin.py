"""Tests for the AdminServer aiohttp middleware — no-auth and dashboard tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from config import Config
from interfaces.admin import AdminServer

_API_SESSIONS = "/api/sessions"
_HTTP_OK = 200
_HTTP_UNAUTHORIZED = 401

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin dashboard"),
]


def _make_app(cfg=None) -> web.Application:
    return AdminServer(MagicMock(), cfg or MagicMock(), port=0)._app


@allure.story("No-auth mode")
@allure.title("Admin API requests pass through the auth middleware when beta auth is disabled")
@pytest.mark.asyncio
async def test_middleware_no_token_allows_api() -> None:
    """Without beta auth (local dev), all API requests pass through."""
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


@allure.story("No-auth mode")
@allure.title("Non-API dashboard routes bypass the admin check even when beta auth is enabled")
@pytest.mark.asyncio
async def test_middleware_does_not_block_dashboard() -> None:
    """Non-/api/ routes are not subject to the admin check."""
    async with TestClient(TestServer(_make_app(Config(beta_auth_required=True)))) as client:
        resp = await client.get("/")
        assert resp.status not in {_HTTP_UNAUTHORIZED, 403}
