"""Tests for the admin reliability dashboard route and aggregation helper."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_admin import _make_app

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin reliability dashboard"),
]

_HTTP_OK = 200
_HTTP_BAD_REQUEST = 400
_BASE_URL = "/api/admin/reliability"


def _prime_get_db(mock_get_db) -> None:
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)


async def _reliability_request(
    mock_repo: AsyncMock,
    window: str = "24h",
) -> tuple[int, Any]:
    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("{0}?window={1}".format(_BASE_URL, window))
            status = resp.status
            body = await resp.json()
    return status, body


@allure.story("Reliability route")
@allure.title("GET /api/admin/reliability returns 200 with window and rows")
@pytest.mark.asyncio
async def test_reliability_route_returns_rows() -> None:
    """Route returns {window, rows} envelope from the aggregation helper."""
    seeded_rows = [
        {"agent": "Narrator", "event_type": "silent_fallback", "total": 3},
        {"agent": "Director", "event_type": "validation_retry", "total": 1},
    ]
    mock_repo = AsyncMock()

    with patch(
        "interfaces.admin_routes_reliability.reliability_aggregates",
        new=AsyncMock(return_value=seeded_rows),
    ) as agg_mock:
        status, body = await _reliability_request(mock_repo, window="7d")
        agg_mock.assert_awaited_once()
        assert agg_mock.call_args.kwargs.get("window") == "7d"

    assert status == _HTTP_OK
    assert body["window"] == "7d"
    assert body["rows"] == seeded_rows


@allure.story("Reliability route")
@allure.title("GET /api/admin/reliability with unknown window returns 400")
@pytest.mark.asyncio
async def test_reliability_route_rejects_unknown_window() -> None:
    """Unknown window value returns 400 with error message."""
    mock_repo = AsyncMock()
    status, body = await _reliability_request(mock_repo, window="99y")
    assert status == _HTTP_BAD_REQUEST
    assert "window" in body.get("error", "")


@allure.story("Reliability route")
@allure.title("GET /api/admin/reliability with no snapshots returns empty rows")
@pytest.mark.asyncio
async def test_reliability_route_empty_rows() -> None:
    """When no snapshots exist the rows list is empty."""
    mock_repo = AsyncMock()

    with patch(
        "interfaces.admin_routes_reliability.reliability_aggregates",
        new=AsyncMock(return_value=[]),
    ):
        status, body = await _reliability_request(mock_repo, window="24h")

    assert status == _HTTP_OK
    assert body["rows"] == []


@allure.story("Reliability aggregation")
@allure.title("reliability_aggregates filters by the correct time window")
@pytest.mark.asyncio
async def test_reliability_aggregates_window_cutoff() -> None:
    """The helper passes a UTC ``since`` timestamp within the expected window."""
    from db.repo_admin_reliability import reliability_aggregates

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value = []
    mock_session.execute.return_value = mock_result

    before = datetime.now(tz=timezone.utc)
    await reliability_aggregates(mock_session, window="7d")
    after = datetime.now(tz=timezone.utc)

    mock_session.execute.assert_awaited_once()
    bind_params: dict[str, Any] = mock_session.execute.call_args.args[1]
    since: datetime = bind_params["since"]

    expected_min = before - timedelta(days=7, seconds=1)
    expected_max = after - timedelta(days=7) + timedelta(seconds=1)
    assert expected_min < since < expected_max


@allure.story("Reliability aggregation")
@allure.title("reliability_aggregates falls back to 24h for unknown window strings")
@pytest.mark.asyncio
async def test_reliability_aggregates_unknown_window_fallback() -> None:
    """Unknown window strings silently fall back to the 24h default."""
    from db.repo_admin_reliability import reliability_aggregates

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value = []
    mock_session.execute.return_value = mock_result

    before = datetime.now(tz=timezone.utc)
    await reliability_aggregates(mock_session, window="bogus")
    after = datetime.now(tz=timezone.utc)

    bind_params: dict[str, Any] = mock_session.execute.call_args.args[1]
    since: datetime = bind_params["since"]

    expected_min = before - timedelta(hours=24, seconds=1)
    expected_max = after - timedelta(hours=24) + timedelta(seconds=1)
    assert expected_min < since < expected_max
