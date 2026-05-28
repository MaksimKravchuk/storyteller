"""Tests for the ``GameRepository`` facade against a real Postgres."""

from __future__ import annotations

import allure
import pytest
import sqlalchemy

from db import tables as tbl
from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


@allure.epic("Memory & Persistence")
@allure.feature("Game repository")
class TestUpdateSession:
    @allure.story("Session update")
    @allure.title("update_session(state=...) writes state and leaves language untouched")
    @pytest.mark.asyncio
    async def test_update_state_only(self, repo: GameRepository, async_session) -> None:
        row = await repo.sessions.create_web("11111111-1111-1111-1111-111111111111")
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
        row = await repo.sessions.create_web("22222222-2222-2222-2222-222222222222")
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
        row = await repo.sessions.create_web("33333333-3333-3333-3333-333333333333")
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
        player_id = "44444444-4444-4444-4444-444444444444"
        await repo.sessions.create_web(player_id)

        await repo.rollback()

        query_result = await async_session.execute(
            sqlalchemy.select(tbl.sessions).where(tbl.sessions.c.web_player_id == player_id),
        )
        assert query_result.mappings().first() is None
