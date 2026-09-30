"""Tests for story poster persistence and the library join."""

from __future__ import annotations

import uuid as _uuid

import allure
import pytest
import pytest_asyncio

from db.repo_posters import PosterImage
from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db

_TAGLINE = "Fog over the Forum."
_WEBP = "image/webp"


def _playbill(tagline: str = _TAGLINE) -> dict:
    return {"tagline": tagline, "hero": "Gaius", "cast": []}


@pytest_asyncio.fixture
async def saved_story(repo: GameRepository, populated_game_state) -> tuple[str, str]:
    """Save a web story and return ``(player_id, session_id)``."""
    player_id = str(_uuid.uuid4())
    session_row = await repo.sessions.create_web(player_id)
    game_state, kg, events = populated_game_state
    await repo.save_game_state(session_row["id"], game_state, kg, events)
    return player_id, str(session_row["id"])


@allure.epic("Memory & Persistence")
@allure.feature("Story posters")
class TestPosterStore:
    @allure.story("Playbill")
    @allure.title("save_playbill stores a playbill that get_playbill returns without an image")
    @pytest.mark.asyncio
    async def test_playbill_round_trip(self, repo: GameRepository, saved_story) -> None:
        _, session_id = saved_story
        await repo.web_games.posters.save_playbill(session_id, _playbill())

        assert await repo.web_games.posters.get_playbill(session_id) == (_playbill(), False)

    @allure.story("Illustration")
    @allure.title("save_image attaches bytes that get_image returns, and re-saving a playbill keeps them")
    @pytest.mark.asyncio
    async def test_image_round_trip_survives_playbill_update(self, repo: GameRepository, saved_story) -> None:
        _, session_id = saved_story
        posters = repo.web_games.posters
        await posters.save_playbill(session_id, _playbill())
        await posters.save_image(session_id, PosterImage(image_bytes=b"RIFF-webp", mime=_WEBP))
        await posters.save_playbill(session_id, _playbill("Rain."))

        assert await posters.get_image(session_id) == PosterImage(image_bytes=b"RIFF-webp", mime=_WEBP)
        stored = await posters.get_playbill(session_id)
        assert stored is not None
        assert stored[0]["tagline"] == "Rain."
        assert stored[1] is True

    @allure.story("Illustration")
    @allure.title("get_image and get_playbill return None for a story without a poster row")
    @pytest.mark.asyncio
    async def test_missing_poster(self, repo: GameRepository, saved_story) -> None:
        _, session_id = saved_story

        assert await repo.web_games.posters.get_image(session_id) is None
        assert await repo.web_games.posters.get_playbill(session_id) is None

    @allure.story("Library")
    @allure.title("web_games.list joins the playbill and illustration flag, and tolerates stories without one")
    @pytest.mark.asyncio
    async def test_library_list_joins_poster(self, repo: GameRepository, saved_story) -> None:
        player_id, session_id = saved_story
        rows_before = await repo.web_games.list(player_id)
        await repo.web_games.posters.save_playbill(session_id, _playbill())
        await repo.web_games.posters.save_image(session_id, PosterImage(image_bytes=b"x", mime=_WEBP))

        rows_after = await repo.web_games.list(player_id)

        assert (rows_before[0]["playbill"], rows_before[0]["has_poster_image"]) == (None, False)
        assert (rows_after[0]["playbill"], rows_after[0]["has_poster_image"]) == (_playbill(), True)
