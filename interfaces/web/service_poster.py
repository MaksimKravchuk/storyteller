"""Paint an optional illustration onto a story's library playbill (ADR-0020).

Every story already has a free, deterministic playbill (see
:mod:`interfaces.web.playbill`). An illustration is a paid image-model call,
so it only runs when the player asks and the operator has enabled it: at
most once per story and ``poster_daily_image_quota`` times per player per
rolling day, after the beta kill switch/budget check and moderation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config import Config
from db.repo_posters import PosterImage
from db.repository import GameRepository
from engine.moderation import moderate_input
from interfaces.web import beta_policy, poster_art, poster_errors, quota_locks
from interfaces.web.schemas_library import Playbill
from interfaces.web.service_helpers import owned_session_context
from llm.image_client import GeneratedImage
from safety.factory import build_moderator

_QUOTA_WINDOW = timedelta(days=1)
# Painting takes tens of seconds; it gets its own lock so the player's turns
# and game starts (which hold ``player_lock(player_id)``) never wait on it.
_POSTER_LOCK_PREFIX = "poster:"


async def _ensure_daily_quota(repo: GameRepository, cfg: Config, player_id: str) -> None:
    since = datetime.now(timezone.utc) - _QUOTA_WINDOW
    if await repo.web_games.posters.painted_since(player_id, since) >= cfg.poster_daily_image_quota:
        raise poster_errors.PosterQuotaError()


async def _load_playbill(repo: GameRepository, session_id: str) -> Playbill:
    stored = await repo.web_games.posters.get_playbill(session_id)
    if stored is None:
        raise poster_errors.PosterMissingError()
    raw_playbill, has_image = stored
    if has_image:
        raise poster_errors.PosterExistsError()
    return Playbill.model_validate(raw_playbill)


async def _prepare(repo: GameRepository, cfg: Config, player_id: str, game_id: str) -> tuple[str, str]:
    """Run every check that must pass before paying for an image; return (session_id, prompt)."""
    await beta_policy.BetaPolicy(repo, cfg).ensure_open()
    session_id, _ = await owned_session_context(repo, player_id, game_id)
    prompt = poster_art.poster_prompt(await _load_playbill(repo, session_id))
    await _ensure_daily_quota(repo, cfg, player_id)
    await moderate_input(build_moderator(cfg), prompt)
    return session_id, prompt


async def _commit_cost(
    repo: GameRepository,
    player_id: str,
    session_id: str,
    prompt: str,
    image: GeneratedImage,
) -> None:
    """Commit a paid image's cost row before storing it can refuse or fail."""
    cost_row = poster_art.cost_log_entry(session_id, prompt, image)
    await repo.ai_logs.save([cost_row], user_id=player_id)
    await repo.commit()


async def illustrate_poster(repo: GameRepository, cfg: Config, player_id: str, game_id: str) -> None:
    """Generate, cost-log, and store one illustration for an owned story."""
    if not poster_art.posters_available(cfg):
        raise poster_errors.PosterUnavailableError()
    async with quota_locks.player_lock(_POSTER_LOCK_PREFIX + player_id):
        session_id, prompt = await _prepare(repo, cfg, player_id, game_id)
        image = await poster_art.paint(poster_art.default_image_client(cfg), prompt)
        await _commit_cost(repo, player_id, session_id, prompt, image)
        stored = PosterImage(image_bytes=image.image_bytes, mime=image.mime)
        if not await repo.web_games.posters.save_image(session_id, stored):
            raise poster_errors.PosterExistsError()
        await repo.commit()
