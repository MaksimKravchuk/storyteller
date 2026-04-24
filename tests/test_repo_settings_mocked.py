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
    assert stmt.table.name == "admin_settings"


_OVERLONG_MODEL_ID = "x" * 201

_INVALID_PAYLOADS = (
    ("unknown role", ("mastermind", "openai", "gpt-5.4"), "unknown role"),
    ("unknown provider", ("narrator", "cohere", "command-r"), "unknown provider"),
    ("empty model_id", ("narrator", "openai", ""), "model_id"),
    ("overlong model_id", ("narrator", "openai", _OVERLONG_MODEL_ID), "model_id"),
)


@allure.story("set_model")
@allure.title("set_model rejects invalid inputs with ValueError before touching the session")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "provider", "model_id", "expected_match"),
    [(args[0], args[1], args[2], err) for _label, args, err in _INVALID_PAYLOADS],
    ids=[label for label, _args, _err in _INVALID_PAYLOADS],
)
async def test_set_model_rejects_invalid_input(
    role: str,
    provider: str,
    model_id: str,
    expected_match: str,
) -> None:
    session = AsyncMock()
    store = AdminSettingsStore(session)
    with pytest.raises(ValueError, match=expected_match):
        await store.set_model(role, provider, model_id)
    session.execute.assert_not_awaited()
