"""Tests for the AdminServer token-based authentication."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_admin import _make_app

_API_SESSIONS = "/api/sessions"
_HTTP_OK = 200
_HTTP_UNAUTHORIZED = 401


@pytest.fixture
def _app_with_token():
    return _make_app(token="secret")


@pytest.mark.asyncio
async def test_token_rejects_missing_auth(_app_with_token) -> None:
    """With a token configured, requests without Authorization header get 401."""
    async with TestClient(TestServer(_app_with_token)) as client:
        resp = await client.get(_API_SESSIONS)
        assert resp.status == _HTTP_UNAUTHORIZED
        resp_body = await resp.json()
        assert resp_body == {"error": "Unauthorized"}


@pytest.mark.asyncio
async def test_token_rejects_wrong_token(_app_with_token) -> None:
    """Wrong token yields 401."""
    async with TestClient(TestServer(_app_with_token)) as client:
        resp = await client.get(_API_SESSIONS, headers={"Authorization": "Bearer wrong"})
        assert resp.status == _HTTP_UNAUTHORIZED


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
