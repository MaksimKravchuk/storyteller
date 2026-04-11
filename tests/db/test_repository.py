"""Tests for the ``GameRepository`` facade against a real Postgres."""

from __future__ import annotations

import uuid as _uuid

import allure
import pytest
import sqlalchemy

from db import tables as tbl
from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


def _chat_id() -> int:
    return int(_uuid.uuid4().int & 0x7FFFFFFF)


@allure.epic("Memory & Persistence")
@allure.feature("Game repository")
class TestGetOrCreateSession:
    @allure.story("Session bootstrap")
    @allure.title("get_or_create_session inserts a new row for an unknown telegram_chat_id")
    @pytest.mark.asyncio
    async def test_inserts_new_row_for_unknown_chat(self, repo: GameRepository) -> None:
        chat_id = _chat_id()
        row = await repo.get_or_create_session(chat_id)

        assert row["telegram_chat_id"] == chat_id
        assert row["state"] == "idle"
        assert row["language"] == "English"
        assert row["id"]

    @allure.story("Session bootstrap")
    @allure.title("get_or_create_session is idempotent on repeated calls with the same chat_id")
    @pytest.mark.asyncio
    async def test_idempotent_on_second_call(self, repo: GameRepository) -> None:
        chat_id = _chat_id()
        first = await repo.get_or_create_session(chat_id)
        second = await repo.get_or_create_session(chat_id)

        assert first["id"] == second["id"]


@allure.epic("Memory & Persistence")
@allure.feature("Game repository")
class TestUpdateSession:
    @allure.story("Session update")
    @allure.title("update_session(state=...) writes state and leaves language untouched")
    @pytest.mark.asyncio
    async def test_update_state_only(self, repo: GameRepository, async_session) -> None:
        row = await repo.get_or_create_session(_chat_id())
        session_id = row["id"]

        await repo.update_session(session_id, state="playing")

        refreshed = await async_session.execute(
            sqlalchemy.select(tbl.sessions).where(tbl.sessions.c.id == session_id),
        )
        after = refreshed.mappings().one()
        assert after["state"] == "playing"
        assert after["language"] == row["language"]

    @allure.story("Session update")
    @allure.title("update_session(language=...) writes language and leaves state untouched")
    @pytest.mark.asyncio
    async def test_update_language_only(self, repo: GameRepository, async_session) -> None:
        row = await repo.get_or_create_session(_chat_id())
        session_id = row["id"]

        await repo.update_session(session_id, language="Russian")

        refreshed = await async_session.execute(
            sqlalchemy.select(tbl.sessions).where(tbl.sessions.c.id == session_id),
        )
        after = refreshed.mappings().one()
        assert after["language"] == "Russian"
        assert after["state"] == row["state"]

    @allure.story("Session update")
    @allure.title("update_session without kwargs is a no-op and leaves the row unchanged")
    @pytest.mark.asyncio
    async def test_noop_when_no_kwargs(self, repo: GameRepository, async_session) -> None:
        row = await repo.get_or_create_session(_chat_id())
        session_id = row["id"]

        await repo.update_session(session_id)

        refreshed = await async_session.execute(
            sqlalchemy.select(tbl.sessions).where(tbl.sessions.c.id == session_id),
        )
        after = refreshed.mappings().one()
        assert after["state"] == row["state"]
        assert after["language"] == row["language"]


@allure.epic("Memory & Persistence")
@allure.feature("Game repository")
class TestRollback:
    @allure.story("Transaction control")
    @allure.title("rollback discards uncommitted inserts within the active savepoint")
    @pytest.mark.asyncio
    async def test_rollback_discards_insert(self, repo: GameRepository, async_session) -> None:
        chat_id = _chat_id()
        await repo.get_or_create_session(chat_id)

        await repo.rollback()

        query_result = await async_session.execute(
            sqlalchemy.select(tbl.sessions).where(tbl.sessions.c.telegram_chat_id == chat_id),
        )
        assert query_result.mappings().first() is None
