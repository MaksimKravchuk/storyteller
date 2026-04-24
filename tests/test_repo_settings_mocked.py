"""Mocked unit tests for db.repo_settings — complements tests/db/test_repo_settings.py.

The DB-backed tests carry ``pytest.mark.db`` and only run under the
``test-db`` job. These mocked variants exercise the Python-side code
paths (validation, payload construction, result mapping) under the
plain ``test`` job so coverage of ``db/repo_settings.py`` stays above
the 90% floor without a Postgres container.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from db.repo_settings import AdminSettingsStore

pytestmark = [
    allure.epic("Admin panel"),
    allure.feature("Model overrides"),
]


def _make_store_with_rows(rows: list[dict]) -> AdminSettingsStore:
    """Build a store whose ``execute()`` returns the given result mappings."""
    session = AsyncMock()
    mapping_result = MagicMock()
    mapping_result.all.return_value = rows
    query_result = MagicMock()
    query_result.mappings.return_value = mapping_result
    session.execute.return_value = query_result
    return AdminSettingsStore(session)


@allure.story("get_model_overrides")
@allure.title("get_model_overrides returns empty dict when no rows are stored")
@pytest.mark.asyncio
async def test_empty_returns_empty_dict() -> None:
    store = _make_store_with_rows([])
    assert await store.get_model_overrides() == {}


@allure.story("get_model_overrides")
@allure.title("get_model_overrides strips the 'model.' prefix from the key and maps rows to tuples")
@pytest.mark.asyncio
async def test_rows_are_mapped_to_role_tuples() -> None:
    store = _make_store_with_rows(
        [
            {"key": "model.narrator", "provider": "anthropic", "model_id": "claude-opus-4-6"},
            {"key": "model.director", "provider": "openai", "model_id": "gpt-5.4-mini"},
        ]
    )
    result = await store.get_model_overrides()
    assert result == {
        "narrator": ("anthropic", "claude-opus-4-6"),
        "director": ("openai", "gpt-5.4-mini"),
    }


@allure.story("set_model")
@allure.title("set_model runs an UPSERT-shaped statement through the session")
@pytest.mark.asyncio
async def test_set_model_issues_statement() -> None:
    session = AsyncMock()
    store = AdminSettingsStore(session)

    await store.set_model("director", "openai", "gpt-5.4-mini")

    session.execute.assert_awaited_once()
    stmt = session.execute.await_args.args[0]
    # Compiled form is PostgreSQL; we just check the table is right.
    assert stmt.table.name == "admin_settings"


@allure.story("set_model")
@allure.title("set_model rejects an unknown role before touching the session")
@pytest.mark.asyncio
async def test_set_model_rejects_unknown_role() -> None:
    session = AsyncMock()
    store = AdminSettingsStore(session)
    with pytest.raises(ValueError, match="unknown role"):
        await store.set_model("mastermind", "openai", "gpt-5.4")
    session.execute.assert_not_awaited()


@allure.story("set_model")
@allure.title("set_model rejects an unknown provider before touching the session")
@pytest.mark.asyncio
async def test_set_model_rejects_unknown_provider() -> None:
    session = AsyncMock()
    store = AdminSettingsStore(session)
    with pytest.raises(ValueError, match="unknown provider"):
        await store.set_model("narrator", "cohere", "command-r")
    session.execute.assert_not_awaited()


@allure.story("set_model")
@allure.title("set_model rejects an empty model_id before touching the session")
@pytest.mark.asyncio
async def test_set_model_rejects_empty_model_id() -> None:
    session = AsyncMock()
    store = AdminSettingsStore(session)
    with pytest.raises(ValueError, match="model_id"):
        await store.set_model("narrator", "openai", "")
    session.execute.assert_not_awaited()


@allure.story("set_model")
@allure.title("set_model rejects a model_id longer than the stored column's max length")
@pytest.mark.asyncio
async def test_set_model_rejects_overlong_model_id() -> None:
    session = AsyncMock()
    store = AdminSettingsStore(session)
    too_long = "x" * 201
    with pytest.raises(ValueError, match="model_id"):
        await store.set_model("narrator", "openai", too_long)
    session.execute.assert_not_awaited()
