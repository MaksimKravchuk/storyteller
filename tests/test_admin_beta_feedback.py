"""Tests for admin beta-feedback review and export routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from aiohttp.test_utils import TestClient, TestServer

from interfaces.admin import AdminServer

_HTTP_OK = 200
_FEEDBACK_ROUTE = "/api/admin/beta/feedback"
_FEEDBACK_CSV_ROUTE = "/api/admin/beta/feedback.csv"

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin dashboard"),
]


@pytest.fixture
def feedback_repo() -> AsyncMock:
    """Return a repository mock exposing beta feedback rows."""
    repo = AsyncMock()
    repo.feedback.list_recent.return_value = [
        {
            "created_at": "2026-05-24T10:00:00+00:00",
            "user_id": "11111111-1111-1111-1111-111111111111",
            "user_email": "friend@example.com",
            "game_id": "game-abc",
            "session_id": "session-abc",
            "turn_number": 3,
            "category": "bug",
            "setting": "Rome",
            "message": "The scene repeated.",
        },
    ]
    return repo


@allure.story("Beta feedback")
@allure.title("Admin API lists recent beta feedback for review")
@pytest.mark.asyncio
async def test_admin_lists_beta_feedback(feedback_repo: AsyncMock) -> None:
    app = AdminServer(MagicMock(), MagicMock(), port=0)._app
    async with TestClient(TestServer(app)) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=feedback_repo),
        ):
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
            response = await client.get(_FEEDBACK_ROUTE)
            payload = await response.json()

    assert response.status == _HTTP_OK
    assert payload["feedback"][0]["user_email"] == "friend@example.com"
    assert payload["feedback"][0]["turn_number"] == 3
    feedback_repo.feedback.list_recent.assert_awaited_once()


@allure.story("Beta feedback")
@allure.title("Admin API exports beta feedback as CSV")
@pytest.mark.asyncio
async def test_admin_exports_beta_feedback_csv(feedback_repo: AsyncMock) -> None:
    app = AdminServer(MagicMock(), MagicMock(), port=0)._app
    async with TestClient(TestServer(app)) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=feedback_repo),
        ):
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
            response = await client.get(_FEEDBACK_CSV_ROUTE)
            body = await response.text()

    assert response.status == _HTTP_OK
    assert "text/csv" in response.headers["Content-Type"]
    assert "friend@example.com" in body
    assert "The scene repeated." in body


@allure.story("Beta feedback")
@allure.title("Admin CSV export neutralises spreadsheet formulas")
@pytest.mark.asyncio
async def test_admin_feedback_csv_neutralises_formulas(feedback_repo: AsyncMock) -> None:
    feedback_row = feedback_repo.feedback.list_recent.return_value[0]
    feedback_row["message"] = '=HYPERLINK("https://bad.example")'
    feedback_row["user_email"] = " +malicious@example.com"
    app = AdminServer(MagicMock(), MagicMock(), port=0)._app
    async with TestClient(TestServer(app)) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=feedback_repo),
        ):
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
            response = await client.get(_FEEDBACK_CSV_ROUTE)
            body = await response.text()

    assert response.status == _HTTP_OK
    assert "'=HYPERLINK" in body
    assert "' +malicious@example.com" in body
