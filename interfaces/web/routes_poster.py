"""HTTP routes for story-poster illustrations (ADR-0019)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from config import Config
from db.repository import GameRepository
from interfaces.web import action_errors, deps, poster_errors, service_poster
from interfaces.web.beta_auth import get_beta_player_id

router = APIRouter()
PlayerIdDep = Annotated[str, Depends(get_beta_player_id)]
CfgDep = Annotated[Config, Depends(deps.get_cfg)]
RepoDep = Annotated[GameRepository, Depends(deps.get_repo)]

# A story's illustration is painted once and never replaced.
_IMAGE_CACHE_CONTROL = "private, max-age=31536000, immutable"


@router.post("/api/games/{game_id}/poster", status_code=status.HTTP_201_CREATED)
async def paint_poster(
    game_id: str,
    player_id: PlayerIdDep,
    cfg: CfgDep,
    repo: RepoDep,
) -> dict[str, bool]:
    """Paint the one illustration for a caller-owned story's playbill."""
    try:
        await service_poster.illustrate_poster(repo, cfg, player_id, game_id)
    except action_errors.ACTION_ERRORS as exc:
        raise action_errors.to_http_exception(exc) from exc
    except poster_errors.PosterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return {"has_poster_image": True}


@router.get("/api/games/{game_id}/poster")
async def get_poster(
    game_id: str,
    player_id: PlayerIdDep,
    repo: RepoDep,
) -> Response:
    """Return a caller-owned story's illustration, hiding absent/foreign ids as 404."""
    image = await repo.web_games.posters.get_image_for_player(player_id, game_id)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=poster_errors.PosterError.detail)
    return Response(content=image.image_bytes, media_type=image.mime, headers={"Cache-Control": _IMAGE_CACHE_CONTROL})
