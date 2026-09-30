"""Shared fakes for the story-poster tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from db.repo_posters import PosterImage
from interfaces.web import service_poster
from interfaces.web.schemas_library import Playbill, PlaybillCastMember
from llm.image_client import GeneratedImage

StoredPlaybill = tuple[dict, bool]

PLAYER = "11111111-1111-1111-1111-111111111111"
WEBP = "image/webp"
IMAGE_BYTES = b"RIFF-webp"
PROMPT_TOKENS = 120
IMAGE_TOKENS = 4160
_PAINT_MS = 9000
IMAGE = GeneratedImage(
    image_bytes=IMAGE_BYTES,
    mime=WEBP,
    model="gpt-image-1-mini",
    input_tokens=PROMPT_TOKENS,
    output_tokens=IMAGE_TOKENS,
    duration_ms=_PAINT_MS,
)


def playbill() -> Playbill:
    """Return a representative post-prologue playbill."""
    return Playbill(
        tagline="Fog clings to the Forum.",
        setting="Rome, the Ides of March",
        hero="Gaius",
        hero_look="a lean scribe with inky fingers",
        era="44 BC",
        region="Italy",
        place="Forum Romanum",
        place_type="district",
        daypart="morning",
        cast=[PlaybillCastMember(label="Marcus (merchant)", known=True)],
    )


def stored_playbill(*, has_image: bool = False) -> StoredPlaybill:
    """Return ``get_playbill``'s shape for the representative playbill."""
    return playbill().model_dump(), has_image


STORED_DEFAULT = stored_playbill()


def fake_cfg(*, enabled: bool = True, api_key: str | None = "sk-test", quota: int = 3) -> MagicMock:
    """Return a config with poster illustrations switched on by default."""
    cfg = MagicMock(name="Config")
    cfg.poster_images_enabled = enabled
    cfg.openai_api_key = api_key
    cfg.poster_daily_image_quota = quota
    return cfg


def fake_repo(
    owned: bool = True,
    stored: StoredPlaybill | None = STORED_DEFAULT,
    painted_today: int = 0,
) -> MagicMock:
    """Return a repository whose poster/log/ownership calls are async fakes."""
    repo = MagicMock(name="GameRepository")
    session_row = None
    if owned:
        session_row = {"id": "sess-1", "language": "English"}
    repo.web_games.get_by_game = AsyncMock(return_value=session_row)
    posters = repo.web_games.posters
    posters.get_playbill = AsyncMock(return_value=stored)
    posters.save_image = AsyncMock(return_value=True)
    posters.painted_since = AsyncMock(return_value=painted_today)
    posters.get_image_for_player = AsyncMock(return_value=PosterImage(image_bytes=IMAGE_BYTES, mime=WEBP))
    repo.ai_logs.save = AsyncMock()
    repo.commit = AsyncMock()
    return repo


def fake_painter(image: GeneratedImage | Exception = IMAGE) -> MagicMock:
    """Return an image client that returns ``image`` or raises it."""
    client = MagicMock(name="ImageClient")
    if isinstance(image, Exception):
        client.generate = AsyncMock(side_effect=image)
    else:
        client.generate = AsyncMock(return_value=image)
    return client


async def illustrate(repo: MagicMock, cfg: MagicMock, client: MagicMock, moderator: object = None) -> None:
    """Run ``illustrate_poster`` with the beta gate open, ``client`` painting, ``moderator`` wired."""
    with (
        patch.object(service_poster.beta_policy.BetaPolicy, "ensure_open", new=AsyncMock()),
        patch.object(service_poster, "build_moderator", return_value=moderator),
        patch.object(service_poster.poster_art, "default_image_client", return_value=client),
    ):
        await service_poster.illustrate_poster(repo, cfg, PLAYER, "game-1")
