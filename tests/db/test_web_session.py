"""Tests for ``GameRepository.get_or_create_web_session`` against a real Postgres."""

from __future__ import annotations

import uuid as _uuid

import allure
import pytest

from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


def _player_id() -> str:
    return str(_uuid.uuid4())


def _chat_id() -> int:
    return int(_uuid.uuid4().int & 0x7FFFFFFF)


@allure.epic("Memory & Persistence")
@allure.feature("Game repository")
class TestGetOrCreateWebSession:
    @allure.story("Web session bootstrap")
    @allure.title("get_or_create_web_session inserts a new row for an unknown web_player_id")
    @pytest.mark.asyncio
    async def test_inserts_new_row_for_unknown_player(self, repo: GameRepository) -> None:
        player_id = _player_id()
        row = await repo.get_or_create_web_session(player_id)

        assert row["web_player_id"] == player_id
        assert row["telegram_chat_id"] is None
        assert row["state"] == "idle"
        assert row["language"] == "English"
        assert row["id"]

    @allure.story("Web session bootstrap")
    @allure.title("get_or_create_web_session is idempotent on repeated calls with the same player_id")
    @pytest.mark.asyncio
    async def test_idempotent_on_second_call(self, repo: GameRepository) -> None:
        player_id = _player_id()
        first = await repo.get_or_create_web_session(player_id)
        second = await repo.get_or_create_web_session(player_id)

        assert first["id"] == second["id"]

    @allure.story("Web session bootstrap")
    @allure.title("get_or_create_web_session produces distinct session rows for different player_ids")
    @pytest.mark.asyncio
    async def test_distinct_players_get_distinct_sessions(self, repo: GameRepository) -> None:
        first = await repo.get_or_create_web_session(_player_id())
        second = await repo.get_or_create_web_session(_player_id())

        assert first["id"] != second["id"]
        assert first["web_player_id"] != second["web_player_id"]


@allure.epic("Memory & Persistence")
@allure.feature("Game repository")
class TestWebAndTelegramCoexist:
    @allure.story("Web session bootstrap")
    @allure.title("Telegram and web sessions coexist as independent rows in the sessions table")
    @pytest.mark.asyncio
    async def test_telegram_and_web_sessions_are_independent(self, repo: GameRepository) -> None:
        tg_row = await repo.get_or_create_session(_chat_id())
        web_row = await repo.get_or_create_web_session(_player_id())

        assert tg_row["id"] != web_row["id"]
        assert tg_row["telegram_chat_id"] is not None
        assert tg_row["web_player_id"] is None
        assert web_row["telegram_chat_id"] is None
        assert web_row["web_player_id"] is not None
