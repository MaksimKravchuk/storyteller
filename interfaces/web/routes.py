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
from interfaces.web import service
from interfaces.web.deps import get_cfg, get_player_id, get_repo
from interfaces.web.schemas import (
    ActionRequest,
    ActionResponse,
    CharacterCreationInput,
    GameSnapshot,
    StartGameRequest,
)
from interfaces.web.service_helpers import StartGameParams

router = APIRouter()

_STATIC_DIR = Path(__file__).parent / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

PlayerIdDep = Annotated[str, Depends(get_player_id)]
CfgDep = Annotated[Config, Depends(get_cfg)]
RepoDep = Annotated[GameRepository, Depends(get_repo)]


@router.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the single-page HTML shell."""
    return FileResponse(_INDEX_HTML)


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness probe — does not touch the database or any agent."""
    return {"status": "ok"}


@router.get("/api/games/current", response_model=GameSnapshot)
async def get_current_game(
    player_id: PlayerIdDep,
    cfg: CfgDep,
    repo: RepoDep,
) -> GameSnapshot:
    """Return the caller's current game, or 404 if none exists."""
    snapshot = await service.get_current_snapshot(repo, cfg, player_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active game")
    return snapshot


@router.post(
    "/api/games",
    response_model=GameSnapshot,
    status_code=status.HTTP_201_CREATED,
)
async def start_game(
    body: StartGameRequest,
    player_id: PlayerIdDep,
    cfg: CfgDep,
    repo: RepoDep,
) -> GameSnapshot:
    """Start a new game for the caller (replaces any existing one)."""
    start_request = StartGameParams(
        player_id=player_id,
        setting=body.setting,
        language=body.language,
        character=body.character,
    )
    return await service.start_game_for_player(repo, cfg, start_request)


@router.get("/api/character-template", response_model=CharacterCreationInput)
async def get_character_template() -> CharacterCreationInput:
    """Return the canned template character for one-click anonymous start.

    The UI offers a "Use template" button that fetches this and
    pre-populates the onboarding form, so a player who doesn't want to
    enter real personal info can start a game with a plausible default.
    """
    return CharacterCreationInput(
        name=TEMPLATE_CHARACTER.name,
        appearance=TEMPLATE_CHARACTER.appearance,
        inventory=list(TEMPLATE_CHARACTER.inventory),
    )


@router.post("/api/games/{game_id}/actions", response_model=ActionResponse)
async def post_action(
    game_id: str,
    body: ActionRequest,
    player_id: PlayerIdDep,
    cfg: CfgDep,
    repo: RepoDep,
) -> ActionResponse:
    """Submit a player action against an existing game."""
    try:
        return await service.process_turn_for_player(
            repo,
            cfg,
            player_id,
            game_id,
            body.action,
        )
    except service.GameNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active game",
        ) from exc
