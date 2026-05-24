"""HTTP routes for the player's story library."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from config import Config
from db.repository import GameRepository
from interfaces.web import deps, service_library
from interfaces.web.beta_auth import get_beta_player_id
from interfaces.web.schemas import GameSnapshot
from interfaces.web.schemas_library import GameListResponse

router = APIRouter()
_NO_ACTIVE_GAME_DETAIL = "No active game"
PlayerIdDep = Annotated[str, Depends(get_beta_player_id)]
CfgDep = Annotated[Config, Depends(deps.get_cfg)]
RepoDep = Annotated[GameRepository, Depends(deps.get_repo)]


@router.get("/api/games", response_model=GameListResponse)
async def list_games(
    player_id: PlayerIdDep,
    repo: RepoDep,
) -> GameListResponse:
    """Return the caller's non-archived story library."""
    return await service_library.list_games_for_player(repo, player_id)


@router.get("/api/games/{game_id}", response_model=GameSnapshot)
async def get_game(
    game_id: str,
    player_id: PlayerIdDep,
    cfg: CfgDep,
    repo: RepoDep,
) -> GameSnapshot:
    """Return one caller-owned game snapshot, hiding absent/foreign ids as 404."""
    snapshot = await service_library.get_snapshot_for_player_game(repo, cfg, player_id, game_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_ACTIVE_GAME_DETAIL)
    return snapshot


@router.post("/api/games/{game_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_game(
    game_id: str,
    player_id: PlayerIdDep,
    repo: RepoDep,
) -> None:
    """Archive one caller-owned game, hiding absent/foreign ids as 404."""
    archived = await service_library.archive_game_for_player(repo, player_id, game_id)
    if not archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_ACTIVE_GAME_DETAIL)
