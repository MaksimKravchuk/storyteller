"""Coverage for admin user management routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_admin import _make_app

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin user management routes"),
]

_HTTP_OK = 200
_HTTP_NOT_FOUND = 404
_USER_ID = "00000000-0000-0000-0000-000000000001"


def _prime_get_db(mock_get_db) -> None:
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)


@allure.story("User list")
@allure.title("/api/admin/users returns users from the repository")
@pytest.mark.asyncio
async def test_admin_users_returns_users_envelope() -> None:
    users = [{"id": _USER_ID, "email": "player@example.com", "session_count": 2}]
    mock_repo = AsyncMock()
    mock_repo.admin.list_users.return_value = users

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("/api/admin/users")
            body = await resp.json()

    assert resp.status == _HTTP_OK
    assert body == {"users": users}
    mock_repo.admin.list_users.assert_awaited_once_with(email_query=None)


@allure.story("User list")
@allure.title("/api/admin/users?email_query=foo forwards the substring to the repository")
@pytest.mark.asyncio
async def test_admin_users_passes_email_query_to_repo() -> None:
    mock_repo = AsyncMock()
    mock_repo.admin.list_users.return_value = []

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("/api/admin/users?email_query=foo")

    assert resp.status == _HTTP_OK
    mock_repo.admin.list_users.assert_awaited_once_with(email_query="foo")


@allure.story("User detail")
@allure.title("/api/admin/users/{id} returns the invites section in the payload")
@pytest.mark.asyncio
async def test_admin_user_detail_returns_invites_section() -> None:
    payload = {
        "account": {"id": _USER_ID, "email": "player@example.com"},
        "usage": {"call_count": 0, "total_tokens": 0},
        "sessions": [],
        "invites": [{"email": "player@example.com", "status": "accepted"}],
        "feedback": [],
    }
    mock_repo = AsyncMock()
    mock_repo.admin.get_user_detail.return_value = payload

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("/api/admin/users/{0}".format(_USER_ID))
            body = await resp.json()

    assert resp.status == _HTTP_OK
    assert body["invites"] == [{"email": "player@example.com", "status": "accepted"}]


@allure.story("User detail")
@allure.title("/api/admin/users/{id} returns the feedback section in the payload")
@pytest.mark.asyncio
async def test_admin_user_detail_returns_feedback_section() -> None:
    feedback = [{"id": "fb1", "category": "bug", "message": "issue"}]
    payload = {
        "account": {"id": _USER_ID, "email": "player@example.com"},
        "usage": {"call_count": 0, "total_tokens": 0},
        "sessions": [],
        "invites": [],
        "feedback": feedback,
    }
    mock_repo = AsyncMock()
    mock_repo.admin.get_user_detail.return_value = payload

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("/api/admin/users/{0}".format(_USER_ID))
            body = await resp.json()

    assert resp.status == _HTTP_OK
    assert body["feedback"] == feedback


@allure.story("User detail")
@allure.title("/api/admin/users/{id} returns account usage and sessions")
@pytest.mark.asyncio
async def test_admin_user_detail_returns_repository_payload() -> None:
    payload = {
        "account": {"id": _USER_ID, "email": "player@example.com"},
        "usage": {"call_count": 1, "total_tokens": 42},
        "sessions": [{"id": "session-1", "turn_count": 3}],
    }
    mock_repo = AsyncMock()
    mock_repo.admin.get_user_detail.return_value = payload

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("/api/admin/users/{0}".format(_USER_ID))
            body = await resp.json()

    assert resp.status == _HTTP_OK
    assert body == payload
    mock_repo.admin.get_user_detail.assert_awaited_once_with(_USER_ID)


@allure.story("User detail")
@allure.title("/api/admin/users/{id} returns 404 for an unknown user")
@pytest.mark.asyncio
async def test_admin_user_detail_returns_404_when_unknown() -> None:
    mock_repo = AsyncMock()
    mock_repo.admin.get_user_detail.return_value = None

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("/api/admin/users/{0}".format(_USER_ID))
            body = await resp.json()

    assert resp.status == _HTTP_NOT_FOUND
    assert body == {"error": "User not found"}
