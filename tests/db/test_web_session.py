"""Tests for web-player session lifecycle methods on ``GameRepository``."""

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
class TestWebSessionLifecycle:
    @allure.story("Web session bootstrap")
    @allure.title("create_web_session inserts a new row for an unknown web_player_id")
    @pytest.mark.asyncio
    async def test_create_inserts_new_row(self, repo: GameRepository) -> None:
        player_id = _player_id()
        row = await repo.sessions.create_web(player_id)

        assert str(row["web_player_id"]) == player_id
        assert row["telegram_chat_id"] is None
        assert row["state"] == "idle"
        assert row["language"] == "English"
        assert row["id"]

    @allure.story("Web session bootstrap")
    @allure.title("get_latest_web_session returns None when the player has no session yet")
    @pytest.mark.asyncio
    async def test_get_latest_none_for_unknown_player(self, repo: GameRepository) -> None:
        assert await repo.sessions.get_latest_web(_player_id()) is None

    @allure.story("Web session bootstrap")
    @allure.title("create_web_session called twice for one player produces two distinct session rows")
    @pytest.mark.asyncio
    async def test_two_games_produce_two_sessions(self, repo: GameRepository) -> None:
        player_id = _player_id()
        first = await repo.sessions.create_web(player_id)
        second = await repo.sessions.create_web(player_id)

        assert first["id"] != second["id"]
        assert str(first["web_player_id"]) == str(second["web_player_id"]) == player_id

    @allure.story("Web session bootstrap")
    @allure.title("get_latest_web_session returns the most recently created row for the player")
    @pytest.mark.asyncio
    async def test_get_latest_returns_newest(self, repo: GameRepository) -> None:
        player_id = _player_id()
        await repo.sessions.create_web(player_id)
        newest = await repo.sessions.create_web(player_id)

        latest = await repo.sessions.get_latest_web(player_id)
        assert latest is not None
        assert latest["id"] == newest["id"]


@allure.epic("Memory & Persistence")
@allure.feature("Game repository")
class TestWebAndTelegramCoexist:
    @allure.story("Web session bootstrap")
    @allure.title("Telegram and web sessions coexist as independent rows in the sessions table")
    @pytest.mark.asyncio
    async def test_telegram_and_web_sessions_are_independent(self, repo: GameRepository) -> None:
        tg_row = await repo.sessions.create_telegram(_chat_id())
        web_row = await repo.sessions.create_web(_player_id())

        assert tg_row["id"] != web_row["id"]
        assert tg_row["telegram_chat_id"] is not None
        assert tg_row["web_player_id"] is None
        assert web_row["telegram_chat_id"] is None
        assert web_row["web_player_id"] is not None
