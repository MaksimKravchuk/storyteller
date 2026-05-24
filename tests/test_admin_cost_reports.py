"""Tests for admin beta cost summary endpoint."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from aiohttp.test_utils import TestClient, TestServer

from config import Config
from interfaces.admin import AdminServer

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin dashboard"),
    allure.story("Cost telemetry"),
]


@allure.title("Admin beta cost summary returns computed costs without prompt material")
@pytest.mark.asyncio
async def test_admin_beta_cost_summary_redacts_prompt_material() -> None:
    app = AdminServer(MagicMock(), Config(), port=0)._app
    mock_repo = AsyncMock()
    mock_repo.ai_logs.usage_summary.return_value = [
        {
            "user_id": "user-1",
            "session_id": "session-1",
            "game_state_id": "game-1",
            "utc_day": date(2026, 5, 24),
            "model": "gpt-5.4-mini",
            "prompt_tokens": 1_000_000,
            "completion_tokens": 500_000,
            "call_count": 1,
            "missing_usage_count": 0,
            "started_at": None,
            "ended_at": None,
            "system_prompt": "prompt must not appear",
            "messages": [{"content": "secret"}],
            "response_content": "response must not appear",
        },
    ]

    async with TestClient(TestServer(app)) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
            response = await client.get("/api/admin/beta/cost-summary")
            payload = await response.json()

    rendered = repr(payload)

    assert response.status == 200
    assert payload["total"]["estimated_cost_usd"] == "1.250000"
    assert "system_prompt" not in rendered
    assert "messages" not in rendered
    assert "response_content" not in rendered
    assert "secret" not in rendered


@allure.title("Admin beta cost summary rejects invalid date filters")
@pytest.mark.asyncio
async def test_admin_beta_cost_summary_rejects_invalid_datetime() -> None:
    app = AdminServer(MagicMock(), Config(), port=0)._app

    async with TestClient(TestServer(app)) as client:
        response = await client.get("/api/admin/beta/cost-summary?start_at=not-a-date")
        payload = await response.json()

    assert response.status == 400
    assert payload == {"error": "Invalid ISO datetime query parameter"}
