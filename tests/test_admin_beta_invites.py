"""Coverage for admin beta invite management routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_admin import _make_app

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin beta invite routes"),
]

_HTTP_OK = 200
_HTTP_BAD_REQUEST = 400


def _prime_get_db(mock_get_db) -> AsyncMock:
    db_session = AsyncMock()
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=db_session)
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
    return db_session


@allure.story("Beta invites")
@allure.title("GET /api/admin/beta/invites returns invites from the repository")
@pytest.mark.asyncio
async def test_admin_beta_invites_returns_invites_envelope() -> None:
    invites = [{"email": "tester@example.com", "status": "invited"}]
    mock_store = AsyncMock()
    mock_store.list_invites.return_value = invites

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_routes_beta_invites.BetaInviteStore", return_value=mock_store),
        ):
            db_session = _prime_get_db(mock_get_db)
            resp = await client.get("/api/admin/beta/invites")
            body = await resp.json()

    assert resp.status == _HTTP_OK
    assert body == {"invites": invites}
    mock_store.list_invites.assert_awaited_once_with()
    assert mock_get_db.called
    assert db_session.commit.await_count == 0


@allure.story("Beta invites")
@allure.title("GET /api/admin/beta/invites preserves the account_id field on each row")
@pytest.mark.asyncio
async def test_admin_beta_invites_returns_account_id_field() -> None:
    invites = [
        {
            "email": "tester@example.com",
            "status": "invited",
            "account_id": "22222222-2222-2222-2222-222222222222",
        },
    ]
    mock_store = AsyncMock()
    mock_store.list_invites.return_value = invites

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_routes_beta_invites.BetaInviteStore", return_value=mock_store),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("/api/admin/beta/invites")
            body = await resp.json()

    assert resp.status == _HTTP_OK
    assert body["invites"][0]["account_id"] == "22222222-2222-2222-2222-222222222222"


@allure.story("Beta invites")
@allure.title("POST /api/admin/beta/invites normalizes and commits invite")
@pytest.mark.asyncio
async def test_admin_beta_invites_post_normalizes_and_commits() -> None:
    invite = {"email": "tester@example.com", "status": "invited"}
    mock_store = AsyncMock()
    mock_store.upsert_invite.return_value = invite

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_routes_beta_invites.BetaInviteStore", return_value=mock_store),
        ):
            db_session = _prime_get_db(mock_get_db)
            resp = await client.post("/api/admin/beta/invites", json={"email": " Tester@Example.COM "})
            body = await resp.json()

    assert resp.status == _HTTP_OK
    assert body == {"invite": invite}
    mock_store.upsert_invite.assert_awaited_once_with("tester@example.com")
    db_session.commit.assert_awaited_once_with()


@allure.story("Beta invites")
@allure.title("POST /api/admin/beta/invites rejects invalid email")
@pytest.mark.asyncio
async def test_admin_beta_invites_post_rejects_invalid_email() -> None:
    mock_store = AsyncMock()

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_routes_beta_invites.BetaInviteStore", return_value=mock_store),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.post("/api/admin/beta/invites", json={"email": "not-an-email"})
            body = await resp.json()

    assert resp.status == _HTTP_BAD_REQUEST
    assert body == {"error": "Valid email is required"}
    mock_store.upsert_invite.assert_not_awaited()
    assert not mock_get_db.called
