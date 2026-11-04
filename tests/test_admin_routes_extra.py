"""Extra coverage for interfaces.admin_routes — dashboard 404, session detail, conversation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import pytest

from tests.admin_app import admin_client, make_admin_app as _make_app

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin dashboard routes"),
]

_HTTP_OK = 200
_HTTP_NOT_FOUND = 404
_SESSION_ID = "sess-123"
_DETAIL_URL = "/api/sessions/{0}".format(_SESSION_ID)
_CONVO_URL = "/api/sessions/{0}/conversation".format(_SESSION_ID)


def _prime_get_db(mock_get_db) -> None:
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)


@allure.story("Dashboard HTML")
@allure.title("dashboard route returns 404 when the admin_dashboard.html asset is missing from disk")
@pytest.mark.asyncio
async def test_dashboard_returns_404_when_html_missing() -> None:
    """If _DASHBOARD_HTML.exists() is False, dashboard responds with 404."""
    with patch("interfaces.admin_routes._DASHBOARD_HTML") as dash_html:
        dash_html.exists.return_value = False
        async with admin_client(_make_app()) as client:
            resp = await client.get("/")
            status = resp.status_code
            body = resp.text
        assert status == _HTTP_NOT_FOUND
        assert "not found" in body.lower()


@allure.story("Session detail")
@allure.title("session_detail route returns the repository payload when the session exists")
@pytest.mark.asyncio
async def test_session_detail_returns_payload_when_found() -> None:
    """session_detail returns the dict produced by repo.admin.get_session_detail."""
    payload = {"id": _SESSION_ID, "language": "English", "turn_count": 7}
    mock_repo = AsyncMock()
    mock_repo.admin.get_session_detail.return_value = payload

    async with admin_client(_make_app()) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get(_DETAIL_URL)
            assert resp.status_code == _HTTP_OK
            body = resp.json()
            assert body == payload
    mock_repo.admin.get_session_detail.assert_awaited_once_with(_SESSION_ID)


@allure.story("Session detail")
@allure.title("session_detail route returns 404 when the repository reports no matching session")
@pytest.mark.asyncio
async def test_session_detail_returns_404_when_not_found() -> None:
    """session_detail must 404 when repo.admin.get_session_detail returns None."""
    mock_repo = AsyncMock()
    mock_repo.admin.get_session_detail.return_value = None

    async with admin_client(_make_app()) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get(_DETAIL_URL)
            assert resp.status_code == _HTTP_NOT_FOUND
            body = resp.json()
            assert body == {"error": "Session not found"}


@allure.story("List sessions")
@allure.title("list_sessions route surfaces account_email and account_id from the repository payload")
@pytest.mark.asyncio
async def test_list_sessions_returns_account_email_when_owner_exists() -> None:
    rows = [
        {
            "id": _SESSION_ID,
            "web_player_id": "11111111-1111-1111-1111-111111111111",
            "state": "playing",
            "account_id": "11111111-1111-1111-1111-111111111111",
            "account_email": "owner@example.com",
        },
    ]
    mock_repo = AsyncMock()
    mock_repo.admin.list_sessions.return_value = rows

    async with admin_client(_make_app()) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("/api/sessions")
            body = resp.json()

    assert resp.status_code == _HTTP_OK
    assert body["sessions"][0]["account_email"] == "owner@example.com"
    assert body["sessions"][0]["account_id"] == "11111111-1111-1111-1111-111111111111"


@allure.story("List sessions")
@allure.title("list_sessions route serializes orphan rows with null account fields")
@pytest.mark.asyncio
async def test_list_sessions_orphan_renders_null_account_email() -> None:
    rows = [{"id": _SESSION_ID, "account_id": None, "account_email": None}]
    mock_repo = AsyncMock()
    mock_repo.admin.list_sessions.return_value = rows

    async with admin_client(_make_app()) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("/api/sessions")
            body = resp.json()

    assert resp.status_code == _HTTP_OK
    assert body["sessions"][0]["account_email"] is None
    assert body["sessions"][0]["account_id"] is None


@allure.story("Session detail")
@allure.title("session_detail route surfaces account_email inside the session sub-dict")
@pytest.mark.asyncio
async def test_session_detail_returns_account_email() -> None:
    payload = {
        "session": {"id": _SESSION_ID, "account_id": "abc", "account_email": "owner@example.com"},
        "game_state": None,
    }
    mock_repo = AsyncMock()
    mock_repo.admin.get_session_detail.return_value = payload

    async with admin_client(_make_app()) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get(_DETAIL_URL)
            body = resp.json()

    assert resp.status_code == _HTTP_OK
    assert body["session"]["account_email"] == "owner@example.com"
    assert body["session"]["account_id"] == "abc"


@allure.story("Conversation log")
@allure.title("conversation route wraps the repository log list in a log envelope")
@pytest.mark.asyncio
async def test_conversation_returns_log_envelope() -> None:
    """conversation returns {'log': <list>} from repo.admin.get_conversation_log."""
    log_entries = [
        {"role": "player", "text": "Hello"},
        {"role": "npc", "text": "Greetings"},
    ]
    mock_repo = AsyncMock()
    mock_repo.admin.get_conversation_log.return_value = log_entries

    async with admin_client(_make_app()) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get(_CONVO_URL)
            assert resp.status_code == _HTTP_OK
            body = resp.json()
            assert body == {"log": log_entries}
    mock_repo.admin.get_conversation_log.assert_awaited_once_with(_SESSION_ID)
