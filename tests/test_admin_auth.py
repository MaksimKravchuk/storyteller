"""Tests for admin account-role authentication."""

from __future__ import annotations

from typing import Any, Iterator
from unittest.mock import AsyncMock, patch

import allure
import pytest

from config import Config
from interfaces.web.auth_models import SupabaseClaims
from tests.admin_app import admin_client, make_admin_app as _make_app

_API_SESSIONS = "/api/sessions"
_HTTP_OK = 200
_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_BEARER_TOKEN = "Bearer valid.jwt"
_CLAIMS = SupabaseClaims(sub="user-1", email="max@example.com")

pytestmark = [allure.epic("Player Interfaces"), allure.feature("Admin authentication")]


@pytest.fixture
def auth_cfg() -> Config:
    return Config(
        beta_auth_required=True,
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test_key",
        supabase_jwks_url="https://example.supabase.co/auth/v1/.well-known/jwks.json",
    )


@pytest.fixture
def mock_repo() -> Iterator[AsyncMock]:
    repo = AsyncMock()
    repo.admin.list_sessions.return_value = []
    with (
        patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
        patch("interfaces.admin_route_helpers.GameRepository", return_value=repo),
    ):
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
        yield repo


async def _get_sessions(cfg: Config, verify: AsyncMock | None = None) -> int:
    with patch("interfaces.admin_auth.verify_supabase_token", verify or AsyncMock(return_value=_CLAIMS)):
        async with admin_client(_make_app(cfg)) as client:
            resp = await client.get(_API_SESSIONS, headers={"Authorization": _BEARER_TOKEN})
            return resp.status_code


@allure.story("Admin role required")
@allure.title("Admin API returns 401 when no session token is sent")
@pytest.mark.asyncio
async def test_rejects_missing_auth(auth_cfg: Config) -> None:
    async with admin_client(_make_app(auth_cfg)) as client:
        resp = await client.get(_API_SESSIONS)
        assert resp.status_code == _HTTP_UNAUTHORIZED
        assert resp.json() == {"detail": "Unauthorized"}


@allure.story("Admin role required")
@allure.title("Admin API returns 401 when the Supabase token fails verification")
@pytest.mark.asyncio
async def test_rejects_invalid_token(auth_cfg: Config) -> None:
    assert await _get_sessions(auth_cfg, AsyncMock(side_effect=ValueError("bad"))) == _HTTP_UNAUTHORIZED


@allure.story("Admin role required")
@allure.title("Admin API returns 403 for a signed-in account without the admin role, or with no account yet")
@pytest.mark.asyncio
@pytest.mark.parametrize("account", [{"is_admin": False}, None])
async def test_rejects_non_admin(auth_cfg: Config, mock_repo: AsyncMock, account: dict[str, Any] | None) -> None:
    mock_repo.accounts.get_by_supabase_user_id.return_value = account
    assert await _get_sessions(auth_cfg) == _HTTP_FORBIDDEN
    mock_repo.accounts.get_by_supabase_user_id.assert_awaited_with(_CLAIMS.sub)


@allure.story("Admin role accepted")
@allure.title("Admin API lets an account with the admin role through")
@pytest.mark.asyncio
async def test_allows_admin(auth_cfg: Config, mock_repo: AsyncMock) -> None:
    mock_repo.accounts.get_by_supabase_user_id.return_value = {"is_admin": True}
    assert await _get_sessions(auth_cfg) == _HTTP_OK
