"""Paint an optional illustration onto a story's library playbill (ADR-0019).

Every story already has a free, deterministic playbill (see
:mod:`interfaces.web.playbill`). An illustration is a paid image-model call,
so it only runs when the player asks and the operator has enabled it: at
most once per story and ``poster_daily_image_quota`` times per player per
rolling day, after the beta kill switch/budget check and moderation.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from config import Config
from db.repo_posters import PosterImage
from db.repository import GameRepository
from interfaces.web import beta_policy, poster_art, poster_errors, quota_locks
from interfaces.web.schemas_library import Playbill
from interfaces.web.service_helpers import owned_session_context
from llm.image_client import ImageClient
from safety.factory import build_moderator
from safety.result import ModerationDirection

_QUOTA_WINDOW = timedelta(days=1)

ImageClientFactory = Callable[[Config], ImageClient]


async def _ensure_daily_quota(repo: GameRepository, cfg: Config, player_id: str) -> None:
    now = datetime.now(timezone.utc)
    painted = await repo.ai_logs.agent_call_count_for_user(
        player_id,
        poster_art.POSTER_AGENT,
        start_at=now - _QUOTA_WINDOW,
        end_at=now + _QUOTA_WINDOW,
    )
    if painted >= cfg.poster_daily_image_quota:
        raise poster_errors.PosterQuotaError("daily poster quota reached")


async def _ensure_safe(cfg: Config, prompt: str) -> None:
    moderator = build_moderator(cfg)
    if moderator is None:
        return
    moderation = await moderator.check(prompt, direction=ModerationDirection.INPUT)
    if moderation.flagged:
        raise poster_errors.PosterRejectedError(moderator.refusal_message(moderation))


async def _load_playbill(repo: GameRepository, session_id: str) -> Playbill:
    stored = await repo.web_games.posters.get_playbill(session_id)
    if stored is None:
        raise poster_errors.PosterMissingError(session_id)
    raw_playbill, has_image = stored
    if has_image:
        raise poster_errors.PosterExistsError(session_id)
    return Playbill.model_validate(raw_playbill)


async def _prepare(repo: GameRepository, cfg: Config, player_id: str, game_id: str) -> tuple[str, str]:
    """Run every check that must pass before paying for an image; return (session_id, prompt)."""
    await beta_policy.BetaPolicy(repo, cfg).ensure_open()
    session_id, _ = await owned_session_context(repo, player_id, game_id)
    prompt = poster_art.poster_prompt(await _load_playbill(repo, session_id))
    await _ensure_daily_quota(repo, cfg, player_id)
    await _ensure_safe(cfg, prompt)
    return session_id, prompt


async def illustrate_poster(
    repo: GameRepository,
    cfg: Config,
    player_id: str,
    game_id: str,
    client_factory: ImageClientFactory = poster_art.default_image_client,
) -> None:
    """Generate, store, and cost-log one illustration for an owned story."""
    if not poster_art.posters_available(cfg):
        raise poster_errors.PosterUnavailableError("poster illustrations are disabled")
    async with quota_locks.player_lock(player_id):
        session_id, prompt = await _prepare(repo, cfg, player_id, game_id)
        image = await poster_art.paint(client_factory(cfg), prompt)
        stored = PosterImage(image_bytes=image.image_bytes, mime=image.mime)
        await repo.web_games.posters.save_image(session_id, stored)
        cost_row = poster_art.cost_log_entry(session_id, prompt, image)
        await repo.ai_logs.save([cost_row], user_id=player_id)
        await repo.commit()


async def poster_image_for_player(repo: GameRepository, player_id: str, game_id: str) -> PosterImage | None:
    """Return an owned story's illustration, or None when absent or not owned."""
    session_row = await repo.web_games.get_by_game(player_id, game_id)
    if session_row is None:
        return None
    return await repo.web_games.posters.get_image(str(session_row["id"]))
