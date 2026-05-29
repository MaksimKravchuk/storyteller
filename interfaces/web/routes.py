"""HTTP routes for the player web UI.

Route handlers are intentionally thin: parse input, call the service layer,
translate service exceptions to HTTP status codes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from config import Config
from db.repository import GameRepository
from defaults.player_character import TEMPLATE_CHARACTER
from interfaces.web import action_errors, deps, pwa, schemas, service
from interfaces.web.beta_auth import get_beta_player_id
from interfaces.web.readiness import readiness_payload

router = APIRouter()
router.add_api_route("/manifest.webmanifest", pwa.manifest, include_in_schema=False)
router.add_api_route("/sw.js", pwa.service_worker, include_in_schema=False)

_STATIC_DIR = Path(__file__).parent / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"
_START_UNAVAILABLE_DETAIL = "Storyteller is temporarily unable to start games. Please try again later."
_START_FAILED_DETAIL = "Storyteller could not start this game. Please try another premise or try again."
_NO_ACTIVE_GAME_DETAIL = "No active game"
_HTTP_TOO_MANY_REQUESTS = 429

PlayerIdDep = Annotated[str, Depends(get_beta_player_id)]
CfgDep = Annotated[Config, Depends(deps.get_cfg)]
RepoDep = Annotated[GameRepository, Depends(deps.get_repo)]


@router.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the single-page HTML shell."""
    return FileResponse(_INDEX_HTML)


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness probe — does not touch the database or any agent."""
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False, response_model=None)
async def readyz(cfg: CfgDep) -> object:
    """Readiness probe for player-startable demo dependencies."""
    return readiness_payload(cfg)


@router.get("/api/games/current", response_model=schemas.GameSnapshot)
async def get_current_game(
    player_id: PlayerIdDep,
    cfg: CfgDep,
    repo: RepoDep,
) -> schemas.GameSnapshot:
    """Return the caller's current game, or 404 if none exists."""
    snapshot = await service.get_current_snapshot(repo, cfg, player_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_ACTIVE_GAME_DETAIL)
    return snapshot


@router.post(
    "/api/games",
    response_model=schemas.GameSnapshot,
    status_code=status.HTTP_201_CREATED,
)
async def start_game(
    body: schemas.StartGameRequest,
    player_id: PlayerIdDep,
    cfg: CfgDep,
    repo: RepoDep,
) -> schemas.GameSnapshot:
    """Start a new game for the caller (replaces any existing one)."""
    start_request = service.StartGameParams(
        player_id=player_id,
        setting=body.setting,
        language=body.language,
        character=body.character,
    )
    try:
        return await service.start_game_for_player(repo, cfg, start_request)
    except service.BetaAccessDeniedError as exc:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.reason in {"beta_disabled", "global_budget_exhausted"}
            else _HTTP_TOO_MANY_REQUESTS
        )
        raise HTTPException(status_code=status_code, detail=exc.message) from exc
    except service.GameStartUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_START_UNAVAILABLE_DETAIL,
        ) from exc
    except service.GameStartFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_START_FAILED_DETAIL,
        ) from exc


@router.get(
    "/api/character-template",
    response_model=schemas.CharacterCreationInput,
    dependencies=[Depends(get_beta_player_id)],
)
async def get_character_template() -> schemas.CharacterCreationInput:
    """Return the canned template character for one-click anonymous start.

    The UI offers a "Use template" button that fetches this and
    pre-populates the onboarding form, so a player who doesn't want to
    enter real personal info can start a game with a plausible default.
    """
    return schemas.CharacterCreationInput(
        name=TEMPLATE_CHARACTER.name,
        appearance=TEMPLATE_CHARACTER.appearance,
        inventory=list(TEMPLATE_CHARACTER.inventory),
    )


@router.post("/api/games/{game_id}/actions", response_model=schemas.ActionResponse)
async def post_action(
    game_id: str,
    body: schemas.ActionRequest,
    player_id: PlayerIdDep,
    cfg: CfgDep,
    repo: RepoDep,
) -> schemas.ActionResponse:
    """Submit a player action against an existing game."""
    try:
        return await service.process_turn_for_player(
            repo,
            cfg,
            player_id,
            game_id,
            body.action,
        )
    except action_errors.ACTION_ERRORS as exc:
        raise action_errors.to_http_exception(exc) from exc
