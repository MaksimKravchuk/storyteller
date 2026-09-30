"""Tests for story poster persistence and the library join."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone

import allure
import pytest
import pytest_asyncio
from sqlalchemy import select

from db import tables as tbl
from db.repo_posters import PosterImage
from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db

_TAGLINE = "Fog over the Forum."
_WEBP = "image/webp"
_IMAGE = PosterImage(image_bytes=b"RIFF-webp", mime=_WEBP)


def _playbill(tagline: str = _TAGLINE) -> dict:
    return {"tagline": tagline, "hero": "Gaius", "cast": []}


@pytest_asyncio.fixture
async def saved_story(repo: GameRepository, async_session, populated_game_state) -> tuple[str, str, str]:
    """Save a web story and return ``(player_id, session_id, game_id)``."""
    player_id = str(_uuid.uuid4())
    session_row = await repo.sessions.create_web(player_id)
    game_state, kg, events = populated_game_state
    await repo.save_game_state(session_row["id"], game_state, kg, events)
    game_id = await async_session.scalar(
        select(tbl.game_states.c.id).where(tbl.game_states.c.session_id == session_row["id"]),
    )
    return player_id, str(session_row["id"]), str(game_id)


@allure.epic("Memory & Persistence")
@allure.feature("Story posters")
class TestPosterStore:
    @allure.story("Playbill")
    @allure.title("save_playbill stores a playbill that get_playbill returns without an image")
    @pytest.mark.asyncio
    async def test_playbill_round_trip(self, repo: GameRepository, saved_story) -> None:
        _, session_id, _ = saved_story
        await repo.web_games.posters.save_playbill(session_id, _playbill())

        assert await repo.web_games.posters.get_playbill(session_id) == (_playbill(), False)

    @allure.story("Illustration")
    @allure.title("save_image stores one illustration and refuses a second")
    @pytest.mark.asyncio
    async def test_one_image_per_story(self, repo: GameRepository, saved_story) -> None:
        player_id, session_id, game_id = saved_story
        posters = repo.web_games.posters
        await posters.save_playbill(session_id, _playbill())

        assert await posters.save_image(session_id, _IMAGE) is True
        assert await posters.save_image(session_id, PosterImage(image_bytes=b"other", mime=_WEBP)) is False
        assert await posters.get_image_for_player(player_id, game_id) == _IMAGE

    @allure.story("Illustration")
    @allure.title("save_playbill replaces the playbill but keeps the illustration")
    @pytest.mark.asyncio
    async def test_playbill_update_keeps_image(self, repo: GameRepository, saved_story) -> None:
        _, session_id, _ = saved_story
        posters = repo.web_games.posters
        await posters.save_playbill(session_id, _playbill())
        await posters.save_image(session_id, _IMAGE)
        await posters.save_playbill(session_id, _playbill("Rain."))

        assert await posters.get_playbill(session_id) == (_playbill("Rain."), True)

    @allure.story("Illustration")
    @allure.title("get_image_for_player hides other players' stories and stories without an image")
    @pytest.mark.asyncio
    async def test_image_lookup_is_owner_scoped(self, repo: GameRepository, saved_story) -> None:
        player_id, session_id, game_id = saved_story
        posters = repo.web_games.posters
        await posters.save_playbill(session_id, _playbill())

        assert await posters.get_image_for_player(player_id, game_id) is None
        await posters.save_image(session_id, _IMAGE)
        assert await posters.get_image_for_player(str(_uuid.uuid4()), game_id) is None

    @allure.story("Illustration")
    @allure.title("painted_since counts a player's illustrations inside the window")
    @pytest.mark.asyncio
    async def test_painted_since_counts_window(self, repo: GameRepository, saved_story) -> None:
        player_id, session_id, _ = saved_story
        posters = repo.web_games.posters
        await posters.save_playbill(session_id, _playbill())
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        assert await posters.painted_since(player_id, hour_ago) == 0
        await posters.save_image(session_id, _IMAGE)
        assert await posters.painted_since(player_id, hour_ago) == 1

    @allure.story("Illustration")
    @allure.title("painted_since ignores other players and paintings before the window")
    @pytest.mark.asyncio
    async def test_painted_since_scoping(self, repo: GameRepository, saved_story) -> None:
        player_id, session_id, _ = saved_story
        posters = repo.web_games.posters
        await posters.save_playbill(session_id, _playbill())
        await posters.save_image(session_id, _IMAGE)
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        assert await posters.painted_since(player_id, datetime.now(timezone.utc) + timedelta(hours=1)) == 0
        assert await posters.painted_since(str(_uuid.uuid4()), hour_ago) == 0

    @allure.story("Library")
    @allure.title("web_games.list joins the playbill and illustration flag, and tolerates stories without one")
    @pytest.mark.asyncio
    async def test_library_list_joins_poster(self, repo: GameRepository, saved_story) -> None:
        player_id, session_id, _ = saved_story
        rows_before = await repo.web_games.list(player_id)
        await repo.web_games.posters.save_playbill(session_id, _playbill())
        await repo.web_games.posters.save_image(session_id, _IMAGE)

        rows_after = await repo.web_games.list(player_id)

        assert (rows_before[0]["playbill"], rows_before[0]["has_poster_image"]) == (None, False)
        assert (rows_after[0]["playbill"], rows_after[0]["has_poster_image"]) == (_playbill(), True)
