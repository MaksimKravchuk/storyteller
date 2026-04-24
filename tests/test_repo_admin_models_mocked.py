"""Mocked unit tests for db.repo_admin_models.fetch_session_models."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from db.repo_admin_models import fetch_session_models

pytestmark = [
    allure.epic("Admin panel"),
    allure.feature("Session models"),
]


@allure.story("fetch_session_models")
@allure.title("fetch_session_models returns each (agent, model) row with its call count")
@pytest.mark.asyncio
async def test_fetch_session_models_maps_rows() -> None:
    session = AsyncMock()
    rows = [
        {"agent_name": "director", "model": "gpt-5.4-mini", "calls": 42},
        {"agent_name": "narrator", "model": "claude-opus-4-6", "calls": 3},
    ]
    mapping_result = MagicMock()
    mapping_result.all.return_value = rows
    query_result = MagicMock()
    query_result.mappings.return_value = mapping_result
    session.execute.return_value = query_result

    assert await fetch_session_models(session, "sess-xyz") == rows
    session.execute.assert_awaited_once()


@allure.story("fetch_session_models")
@allure.title("fetch_session_models returns an empty list when the session has no AI calls")
@pytest.mark.asyncio
async def test_fetch_session_models_empty() -> None:
    session = AsyncMock()
    mapping_result = MagicMock()
    mapping_result.all.return_value = []
    query_result = MagicMock()
    query_result.mappings.return_value = mapping_result
    session.execute.return_value = query_result

    assert await fetch_session_models(session, "sess-empty") == []
