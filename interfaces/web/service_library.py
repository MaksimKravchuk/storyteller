"""Business logic for the web story library."""

from __future__ import annotations

from config import Config
from db.repository import GameRepository
from interfaces.web.schemas import GameSnapshot
from interfaces.web.schemas_library import GameListResponse
from interfaces.web.service_helpers import (
    game_summary_from_row,
    restore_engine,
    session_language,
    snapshot_from_engine,
)


async def list_games_for_player(repo: GameRepository, player_id: str) -> GameListResponse:
    """Return the caller's non-archived games for the My Stories library."""
    rows = await repo.web_games.list(player_id)
    return GameListResponse(games=[game_summary_from_row(row) for row in rows])


async def get_snapshot_for_player_game(
    repo: GameRepository,
    cfg: Config,
    player_id: str,
    game_id: str,
) -> GameSnapshot | None:
    """Return one owned game snapshot, or ``None`` for absent/foreign/archived ids."""
    session_row = await repo.web_games.get_by_game(player_id, game_id)
    if session_row is None:
        return None
    engine = await restore_engine(repo, cfg, session_row)
    if engine is None:
        return None
    return snapshot_from_engine(engine, session_language(session_row))


async def archive_game_for_player(repo: GameRepository, player_id: str, game_id: str) -> bool:
    """Archive one owned game and commit, returning False for absent/foreign ids."""
    archived = await repo.web_games.archive(player_id, game_id)
    if not archived:
        return False
    await repo.commit()
    return True
