"""Tests for on-demand poster illustrations: prompt and service guards."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from db.repo_posters import PosterImage
from interfaces.web import poster_art, poster_errors, service_poster
from interfaces.web.errors import GameNotFoundError
from tests._poster_helpers import (
    PLAYER,
    WEBP,
    fake_cfg,
    fake_painter,
    fake_repo,
    illustrate,
    playbill,
    stored_playbill,
)

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]

_STORY = "Story posters"


@allure.story(_STORY)
@allure.title("poster_prompt paints the hero and place but never names the cast")
def test_prompt_uses_hero_and_place_not_cast() -> None:
    prompt = poster_art.poster_prompt(playbill())

    assert "a lean scribe with inky fingers" in prompt
    assert "Forum Romanum" in prompt
    assert "Rome, the Ides of March" in prompt
    assert "Marcus" not in prompt
    assert "No text" in prompt


@allure.story(_STORY)
@allure.title("posters_available needs both the operator flag and an OpenAI key")
@pytest.mark.parametrize(
    ("enabled", "api_key", "expected"),
    [(True, "sk-test", True), (False, "sk-test", False), (True, None, False), (True, "", False)],
)
def test_posters_available(enabled: bool, api_key: str | None, expected: bool) -> None:
    assert poster_art.posters_available(fake_cfg(enabled=enabled, api_key=api_key)) is expected


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("illustrate_poster stores the image, logs its cost as a PosterIllustrator call, and commits")
async def test_illustrate_stores_logs_and_commits() -> None:
    repo, client = fake_repo(stored=stored_playbill()), fake_painter()

    await illustrate(repo, fake_cfg(), client)

    save_image = repo.web_games.posters.save_image
    save_image.assert_awaited_once_with("sess-1", PosterImage(image_bytes=b"RIFF-webp", mime=WEBP))
    log_call = repo.ai_logs.save.await_args
    logged_rows = log_call.args[0]
    assert log_call.kwargs == {"user_id": PLAYER}
    assert logged_rows[0]["agent_name"] == "PosterIllustrator"
    assert (logged_rows[0]["prompt_tokens"], logged_rows[0]["completion_tokens"]) == (120, 4160)
    assert logged_rows[0]["model"] == "gpt-image-1-mini"
    repo.commit.assert_awaited_once_with()
    assert "Forum Romanum" in client.generate.await_args.args[0]


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("illustrate_poster counts today's PosterIllustrator calls for this player")
async def test_illustrate_checks_daily_count_for_poster_agent() -> None:
    repo = fake_repo(stored=stored_playbill())

    await illustrate(repo, fake_cfg(), fake_painter())

    count_call = repo.ai_logs.agent_call_count_for_user.await_args
    assert count_call.args == (PLAYER, "PosterIllustrator")


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("illustrate_poster refuses before any paid call when illustrations are unavailable")
@pytest.mark.parametrize(("enabled", "api_key"), [(False, "sk-test"), (True, None)])
async def test_illustrate_unavailable(enabled: bool, api_key: str | None) -> None:
    repo, client = fake_repo(stored=stored_playbill()), fake_painter()

    with pytest.raises(poster_errors.PosterUnavailableError):
        await illustrate(repo, fake_cfg(enabled=enabled, api_key=api_key), client)

    client.generate.assert_not_awaited()


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("illustrate_poster hides stories the player does not own")
async def test_illustrate_not_owned() -> None:
    repo, client = fake_repo(owned=False, stored=stored_playbill()), fake_painter()

    with pytest.raises(GameNotFoundError):
        await illustrate(repo, fake_cfg(), client)

    client.generate.assert_not_awaited()


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("illustrate_poster refuses stories without a playbill or with an illustration already")
@pytest.mark.parametrize(
    ("stored", "error"),
    [(None, poster_errors.PosterMissingError), (stored_playbill(has_image=True), poster_errors.PosterExistsError)],
)
async def test_illustrate_needs_bare_playbill(stored: tuple[dict, bool] | None, error: type[Exception]) -> None:
    repo, client = fake_repo(stored=stored), fake_painter()

    with pytest.raises(error):
        await illustrate(repo, fake_cfg(), client)

    client.generate.assert_not_awaited()


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("illustrate_poster stops at the daily quota before paying for an image")
async def test_illustrate_quota_reached() -> None:
    repo, client = fake_repo(stored=stored_playbill(), painted_today=3), fake_painter()

    with pytest.raises(poster_errors.PosterQuotaError):
        await illustrate(repo, fake_cfg(quota=3), client)

    client.generate.assert_not_awaited()


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("illustrate_poster refuses a prompt that moderation flags, with the moderator's message")
async def test_illustrate_moderation_flagged() -> None:
    repo, client = fake_repo(stored=stored_playbill()), fake_painter()
    moderator = MagicMock()
    moderator.check = AsyncMock(return_value=MagicMock(flagged=True))
    moderator.refusal_message = MagicMock(return_value="Let's keep the poster within the story's limits.")

    with pytest.raises(poster_errors.PosterRejectedError, match="within the story's limits"):
        await illustrate(repo, fake_cfg(), client, moderator=moderator)

    client.generate.assert_not_awaited()


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("illustrate_poster reports a provider failure without storing, logging, or committing")
async def test_illustrate_provider_failure() -> None:
    repo = fake_repo(stored=stored_playbill())

    with pytest.raises(poster_errors.PosterFailedError):
        await illustrate(repo, fake_cfg(), fake_painter(RuntimeError("provider down")))

    save_image = repo.web_games.posters.save_image
    save_image.assert_not_awaited()
    repo.ai_logs.save.assert_not_awaited()
    repo.commit.assert_not_awaited()


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("poster_image_for_player never reads the image of a story the player does not own")
async def test_image_lookup_is_owner_scoped() -> None:
    owned, foreign = fake_repo(), fake_repo(owned=False)

    assert await service_poster.poster_image_for_player(owned, PLAYER, "game-1") == PosterImage(
        image_bytes=b"RIFF-webp",
        mime=WEBP,
    )
    assert await service_poster.poster_image_for_player(foreign, PLAYER, "game-1") is None
    get_image = foreign.web_games.posters.get_image
    get_image.assert_not_awaited()
