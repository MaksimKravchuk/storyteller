"""Tests for the story-poster HTTP routes."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from fastapi.testclient import TestClient

from interfaces.web import beta_auth, poster_errors, service_poster
from interfaces.web.app import app
from interfaces.web.deps import get_cfg, get_repo
from interfaces.web.errors import GameNotFoundError
from safety.moderator import SafetyRejectedError
from tests._poster_helpers import PLAYER, WEBP, fake_cfg, fake_repo

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]

_STORY = "Story posters"


@pytest.fixture
def poster_client() -> Iterator[TestClient]:
    cfg, repo = fake_cfg(), fake_repo()
    app.dependency_overrides[get_cfg] = lambda: cfg
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[beta_auth.get_beta_player_id] = lambda: PLAYER
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@allure.story(_STORY)
@allure.title("POST /api/games/{id}/poster returns 201 once the illustration is stored")
def test_route_paint_created(poster_client: TestClient) -> None:
    with patch.object(service_poster, "illustrate_poster", new=AsyncMock()):
        response = poster_client.post("/api/games/game-1/poster")

    assert response.status_code == 201
    assert response.json() == {"has_poster_image": True}


@allure.story(_STORY)
@allure.title("POST /api/games/{id}/poster maps each refusal to a player-safe status")
@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (poster_errors.PosterUnavailableError("off"), 404),
        (poster_errors.PosterMissingError("s"), 404),
        (GameNotFoundError(PLAYER), 404),
        (poster_errors.PosterExistsError("s"), 409),
        (poster_errors.PosterQuotaError("q"), 429),
        (SafetyRejectedError("Not that.", MagicMock()), 400),
        (poster_errors.PosterFailedError("down"), 503),
        (service_poster.beta_policy.BetaAccessDeniedError("Paused.", reason="beta_disabled"), 503),
        (service_poster.beta_policy.BetaAccessDeniedError("Limit.", reason="daily_turn_quota"), 429),
    ],
)
def test_route_paint_errors(poster_client: TestClient, error: Exception, status_code: int) -> None:
    with patch.object(service_poster, "illustrate_poster", new=AsyncMock(side_effect=error)):
        response = poster_client.post("/api/games/game-1/poster")

    assert response.status_code == status_code
    assert "Traceback" not in response.text


@allure.story(_STORY)
@allure.title("GET /api/games/{id}/poster serves the stored image as an immutable private resource")
def test_route_get_image(poster_client: TestClient) -> None:
    response = poster_client.get("/api/games/game-1/poster")

    assert response.status_code == 200
    assert response.headers["content-type"] == WEBP
    assert response.content == b"RIFF-webp"
    assert response.headers["cache-control"] == "private, max-age=31536000, immutable"


@allure.story(_STORY)
@allure.title("GET /api/games/{id}/poster is 404 when the player's story has no illustration")
def test_route_get_image_missing(poster_client: TestClient) -> None:
    repo = app.dependency_overrides[get_repo]()
    repo.web_games.posters.get_image_for_player = AsyncMock(return_value=None)

    response = poster_client.get("/api/games/game-1/poster")

    assert response.status_code == 404
    repo.web_games.posters.get_image_for_player.assert_awaited_once_with(PLAYER, "game-1")
