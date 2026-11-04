"""Budget guard reads one aggregate row per model, not the per-session/day breakdown."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest
from sqlalchemy.dialects import postgresql

from db.repo_ai_logs import AILogStore, _usage_by_model_stmt

pytestmark = [allure.epic("Persistence"), allure.feature("AI call logs"), allure.story("Budget usage")]


@allure.title("usage_by_model statement groups by model only and sums tokens in SQL")
def test_usage_by_model_stmt_groups_by_model_only() -> None:
    sql = str(_usage_by_model_stmt().compile(dialect=postgresql.dialect())).lower()

    group_by = sql.split("group by", 1)[1]
    assert group_by.strip() == "ai_call_logs.model"
    assert "sum(ai_call_logs.prompt_tokens)" in sql


@allure.title("usage_by_model returns plain dict rows")
@pytest.mark.asyncio
async def test_usage_by_model_returns_dicts() -> None:
    session = MagicMock()
    result = MagicMock()
    result.mappings.return_value = [{"model": "gpt-x", "prompt_tokens": 3}]
    session.execute = AsyncMock(return_value=result)

    assert await AILogStore(session).usage_by_model() == [{"model": "gpt-x", "prompt_tokens": 3}]
