"""Tests for web-player session lifecycle methods on ``GameRepository``."""

from __future__ import annotations

import uuid as _uuid

import allure
import pytest

from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


def _player_id() -> str:
    return str(_uuid.uuid4())


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
