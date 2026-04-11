"""Tests for the AdminServer token-based authentication."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_admin import _make_app

_API_SESSIONS = "/api/sessions"
_HTTP_OK = 200
_HTTP_UNAUTHORIZED = 401

pytestmark = [allure.epic("Player Interfaces"), allure.feature("Admin authentication")]


@pytest.fixture
def _app_with_token():
    return _make_app(token="secret")


@allure.story("Token required")
@allure.title("Admin API returns 401 Unauthorized when no Authorization header is sent and a token is configured")
@pytest.mark.asyncio
async def test_token_rejects_missing_auth(_app_with_token) -> None:
    """With a token configured, requests without Authorization header get 401."""
    async with TestClient(TestServer(_app_with_token)) as client:
        resp = await client.get(_API_SESSIONS)
        assert resp.status == _HTTP_UNAUTHORIZED
        resp_body = await resp.json()
        assert resp_body == {"error": "Unauthorized"}


@allure.story("Token required")
@allure.title("Admin API returns 401 Unauthorized when the Bearer token does not match the configured value")
@pytest.mark.asyncio
async def test_token_rejects_wrong_token(_app_with_token) -> None:
    """Wrong token yields 401."""
    async with TestClient(TestServer(_app_with_token)) as client:
        resp = await client.get(_API_SESSIONS, headers={"Authorization": "Bearer wrong"})
        assert resp.status == _HTTP_UNAUTHORIZED


@allure.story("Token accepted")
@allure.title("Admin API allows the request through with a 200 response when the correct Bearer token is provided")
@pytest.mark.asyncio
async def test_token_allows_correct_token(_app_with_token) -> None:
    """Correct Bearer token allows the request through."""
    async with TestClient(TestServer(_app_with_token)) as client:
        mock_repo = AsyncMock()
        mock_repo.admin.list_sessions.return_value = []
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
            resp = await client.get(_API_SESSIONS, headers={"Authorization": "Bearer secret"})
            assert resp.status == _HTTP_OK
