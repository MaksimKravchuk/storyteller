"""Business logic for the web interface.

Thin layer between FastAPI routes and the underlying engine/repository.
Keeps route handlers free of engine wiring so they can be trivially tested
via ``app.dependency_overrides``.
"""

from __future__ import annotations

from loguru import logger

from config import Config
from db.repository import GameRepository
from engine.factory import create_engine
from engine.game_engine import GameEngine
from interfaces.web.character import build_character_info
from interfaces.web.schemas import ActionResponse, GameSnapshot
from interfaces.web.transcript import render_narrator_html
from interfaces.web.service_helpers import (
    persist_engine,
    restore_engine,
    snapshot_from_engine,
)
from llm.call_logger import current_session_id, reset_buffer
from llm.turn_event_logger import reset_events

_STATE_PLAYING = "playing"


class GameNotFoundError(Exception):
    """Raised when a web player has no active game (or an unknown game_id)."""


class GameOwnershipError(Exception):
    """Raised when a player attempts to act on a game that is not theirs."""


async def get_current_snapshot(
    repo: GameRepository,
    cfg: Config,
    player_id: str,
) -> GameSnapshot | None:
    """Return the current game snapshot for a web player, or ``None`` if none exists."""
    session_row = await repo.sessions.get_latest_web(player_id)
    if session_row is None:
        return None
    engine = await restore_engine(repo, cfg, session_row)
    if engine is None:
        return None
    return snapshot_from_engine(engine)


async def _start_and_persist(
    repo: GameRepository,
    session_id: str,
    engine: GameEngine,
    setting: str,
) -> None:
    """Run ``start_game`` and persist the resulting state in one call."""
    await engine.start_game(setting)
    await persist_engine(repo, session_id, engine, turn_number=None)


async def start_game_for_player(
    repo: GameRepository,
    cfg: Config,
    player_id: str,
    setting: str,
    language: str,
) -> GameSnapshot:
    """Create a fresh session for this web player and return the opening snapshot."""
    session_row = await repo.sessions.create_web(player_id)
    session_id = session_row["id"]

    current_session_id.set(session_id)
    reset_buffer()
    reset_events()
    engine = create_engine(cfg, language=language)
    try:
        await _start_and_persist(repo, session_id, engine, setting)
    except Exception:
        logger.exception("Failed to start web game for player {}", player_id)
        await repo.rollback()
        raise
    await repo.sessions.update(session_id, state=_STATE_PLAYING, language=language)
    return snapshot_from_engine(engine)


async def _act_and_persist(
    repo: GameRepository,
    session_id: str,
    engine: GameEngine,
    action: str,
) -> ActionResponse:
    """Run a player action through the engine and persist the new state."""
    narration = await engine.process_action(action)
    game_state = engine.game_state
    if game_state is None:
        raise RuntimeError("engine.game_state is None — engine did not initialise correctly")
    turn_number = game_state.turn_count
    await persist_engine(repo, session_id, engine, turn_number=turn_number)
    return ActionResponse(
        narration=narration,
        narration_html=render_narrator_html(narration),
        turn_count=turn_number,
        character=build_character_info(game_state),
    )


async def process_turn_for_player(
    repo: GameRepository,
    cfg: Config,
    player_id: str,
    game_id: str,
    action: str,
) -> ActionResponse:
    """Process a player action on an existing game.

    Raises ``GameNotFoundError`` if the player has no game and
    ``GameOwnershipError`` if the supplied ``game_id`` doesn't match.
    """
    session_row = await repo.sessions.get_latest_web(player_id)
    if session_row is None:
        raise GameNotFoundError(player_id)
    session_id = session_row["id"]
    engine = await restore_engine(repo, cfg, session_row)
    if engine is None:
        raise GameNotFoundError(player_id)
    if str(engine.game_state.uuid) != game_id:  # type: ignore[union-attr]
        raise GameOwnershipError(player_id)

    current_session_id.set(session_id)
    reset_buffer()
    reset_events()
    return await _act_and_persist(repo, session_id, engine, action)
