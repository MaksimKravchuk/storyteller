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
class TestTelegramSessionLifecycle:
    @allure.story("Session bootstrap")
    @allure.title("create_telegram_session inserts a new row and returns defaults")
    @pytest.mark.asyncio
    async def test_create_inserts_new_row(self, repo: GameRepository) -> None:
        chat_id = _chat_id()
        row = await repo.sessions.create_telegram(chat_id)

        assert row["telegram_chat_id"] == chat_id
        assert row["state"] == "idle"
        assert row["language"] == "English"
        assert row["id"]

    @allure.story("Session bootstrap")
    @allure.title("get_latest_telegram_session returns None when no session exists for the chat")
    @pytest.mark.asyncio
    async def test_get_latest_none_for_unknown_chat(self, repo: GameRepository) -> None:
        assert await repo.sessions.get_latest_telegram(_chat_id()) is None

    @allure.story("Session bootstrap")
    @allure.title("create_telegram_session called twice produces two rows with distinct ids")
    @pytest.mark.asyncio
    async def test_two_games_produce_two_sessions(self, repo: GameRepository) -> None:
        chat_id = _chat_id()
        first = await repo.sessions.create_telegram(chat_id)
        second = await repo.sessions.create_telegram(chat_id)

        assert first["id"] != second["id"]
        assert first["telegram_chat_id"] == second["telegram_chat_id"] == chat_id

    @allure.story("Session bootstrap")
    @allure.title("get_latest_telegram_session returns the most recently created row")
    @pytest.mark.asyncio
    async def test_get_latest_returns_newest(self, repo: GameRepository) -> None:
        chat_id = _chat_id()
        await repo.sessions.create_telegram(chat_id)
        newest = await repo.sessions.create_telegram(chat_id)

        latest = await repo.sessions.get_latest_telegram(chat_id)
        assert latest is not None
        assert latest["id"] == newest["id"]


@allure.epic("Memory & Persistence")
@allure.feature("Game repository")
class TestUpdateSession:
    @allure.story("Session update")
    @allure.title("update_session(state=...) writes state and leaves language untouched")
    @pytest.mark.asyncio
    async def test_update_state_only(self, repo: GameRepository, async_session) -> None:
        row = await repo.sessions.create_telegram(_chat_id())
        session_id = row["id"]

        await repo.sessions.update(session_id, state="playing")

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
        row = await repo.sessions.create_telegram(_chat_id())
        session_id = row["id"]

        await repo.sessions.update(session_id, language="Russian")

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
        row = await repo.sessions.create_telegram(_chat_id())
        session_id = row["id"]

        await repo.sessions.update(session_id)

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
        await repo.sessions.create_telegram(chat_id)

        await repo.rollback()

        query_result = await async_session.execute(
            sqlalchemy.select(tbl.sessions).where(tbl.sessions.c.telegram_chat_id == chat_id),
        )
        assert query_result.mappings().first() is None
