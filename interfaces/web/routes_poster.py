"""HTTP routes for story-poster illustrations (ADR-0019)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from config import Config
from db.repository import GameRepository
from interfaces.web import deps, poster_errors, service_poster
from interfaces.web.beta_auth import get_beta_player_id
from interfaces.web.beta_policy import BetaAccessDeniedError
from interfaces.web.errors import GameNotFoundError

router = APIRouter()
PlayerIdDep = Annotated[str, Depends(get_beta_player_id)]
CfgDep = Annotated[Config, Depends(deps.get_cfg)]
RepoDep = Annotated[GameRepository, Depends(deps.get_repo)]

_NO_POSTER_DETAIL = "No poster for this story"
_POSTER_EXISTS_DETAIL = "This story already has its poster."
_POSTER_QUOTA_DETAIL = "You have painted today's posters. Try again tomorrow."
_POSTER_FAILED_DETAIL = "The painter could not finish this poster. Please try again later."
_HTTP_TOO_MANY_REQUESTS = 429
_HTTP_UNPROCESSABLE_ENTITY = 422
_IMAGE_CACHE_CONTROL = "private, max-age=86400"
_POSTER_ERRORS = (BetaAccessDeniedError, GameNotFoundError, poster_errors.PosterError)
_NOT_FOUND_ERRORS = (GameNotFoundError, poster_errors.PosterMissingError, poster_errors.PosterUnavailableError)
_STATUS_BY_ERROR = (
    (poster_errors.PosterExistsError, status.HTTP_409_CONFLICT, _POSTER_EXISTS_DETAIL),
    (poster_errors.PosterQuotaError, _HTTP_TOO_MANY_REQUESTS, _POSTER_QUOTA_DETAIL),
    (poster_errors.PosterFailedError, status.HTTP_503_SERVICE_UNAVAILABLE, _POSTER_FAILED_DETAIL),
)


def _to_http_exception(exc: Exception) -> HTTPException:
    """Map a poster service refusal to its HTTP response."""
    if isinstance(exc, BetaAccessDeniedError):
        hard_stop = exc.reason in {"beta_disabled", "global_budget_exhausted"}
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE if hard_stop else _HTTP_TOO_MANY_REQUESTS
        return HTTPException(status_code=status_code, detail=exc.message)
    if isinstance(exc, _NOT_FOUND_ERRORS):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_POSTER_DETAIL)
    if isinstance(exc, poster_errors.PosterRejectedError):
        return HTTPException(status_code=_HTTP_UNPROCESSABLE_ENTITY, detail=str(exc))
    for error_type, status_code, detail in _STATUS_BY_ERROR:
        if isinstance(exc, error_type):
            return HTTPException(status_code=status_code, detail=detail)
    raise exc


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
    except _POSTER_ERRORS as exc:
        raise _to_http_exception(exc) from exc
    return {"has_poster_image": True}


@router.get("/api/games/{game_id}/poster")
async def get_poster(
    game_id: str,
    player_id: PlayerIdDep,
    repo: RepoDep,
) -> Response:
    """Return a caller-owned story's illustration, hiding absent/foreign ids as 404."""
    image = await service_poster.poster_image_for_player(repo, player_id, game_id)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_POSTER_DETAIL)
    return Response(content=image.image_bytes, media_type=image.mime, headers={"Cache-Control": _IMAGE_CACHE_CONTROL})
