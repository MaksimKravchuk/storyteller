"""Business logic for the web interface.

Thin layer between FastAPI routes and the underlying engine/repository.
Keeps route handlers free of engine wiring so they can be trivially tested
via ``app.dependency_overrides``.
"""

from __future__ import annotations

from loguru import logger

from config import Config
from db.repository import GameRepository
from engine.session_ops import begin_session, persist_engine_state, resume_session
from interfaces.web.character import build_character_info
from interfaces.web.errors import GameNotFoundError, GameStartUnavailableError, is_provider_auth_error
from interfaces.web.schemas import ActionResponse, CharacterCreationInput, GameSnapshot
from interfaces.web.transcript import render_narrator_html
from interfaces.web.service_helpers import (
    StartGameParams,
    restore_engine,
    session_language,
    snapshot_from_engine,
)
from models.player_character_input import PlayerCharacterInput

_STATE_PLAYING = "playing"


def _to_engine_character(character: CharacterCreationInput | None) -> PlayerCharacterInput | None:
    """Convert wire-side character to engine-layer; return None for blank payloads."""
    if character is None:
        return None
    if not character.name and not character.appearance and not character.inventory:
        return None
    return PlayerCharacterInput(
        name=character.name,
        appearance=character.appearance,
        inventory=list(character.inventory),
    )


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
    return snapshot_from_engine(engine, session_language(session_row))


async def _start_and_persist(
    repo: GameRepository,
    session_id: str,
    engine,
    setting: str,
    character: PlayerCharacterInput | None,
) -> None:
    """Run ``start_game`` and persist the resulting state in one call."""
    await engine.start_game(setting, character=character)
    await persist_engine_state(repo, session_id, engine, turn_number=None)


async def _mark_session_playing(repo: GameRepository, session_id: str, language: str) -> None:
    """Mark the new web session playable before returning to the client."""
    await repo.sessions.update(session_id, state=_STATE_PLAYING, language=language)
    await repo.commit()


async def start_game_for_player(
    repo: GameRepository,
    cfg: Config,
    start_request: StartGameParams,
) -> GameSnapshot:
    """Create a fresh session for this web player and return the opening snapshot."""
    session_row = await repo.sessions.create_web(start_request.player_id)
    session_id = session_row["id"]

    engine = await begin_session(repo, cfg, session_id, start_request.language)
    try:
        await _start_and_persist(
            repo,
            session_id,
            engine,
            start_request.setting,
            _to_engine_character(start_request.character),
        )
    except Exception as exc:
        logger.exception("Failed to start web game for player {}", start_request.player_id)
        await repo.rollback()
        if is_provider_auth_error(exc):
            raise GameStartUnavailableError("LLM provider credentials rejected game start") from exc
        raise
    await _mark_session_playing(repo, session_id, start_request.language)
    return snapshot_from_engine(engine, start_request.language)


async def _act_and_persist(
    repo: GameRepository,
    session_id: str,
    engine,
    action: str,
    language: str,
) -> ActionResponse:
    """Run a player action through the engine and persist the new state."""
    try:
        narration = await engine.process_action(action)
    except Exception as exc:
        if is_provider_auth_error(exc):
            raise GameStartUnavailableError("LLM provider credentials rejected player action") from exc
        raise
    game_state, _, _ = engine.assert_running()
    turn_number = game_state.turn_count
    await persist_engine_state(repo, session_id, engine, turn_number=turn_number)
    await repo.commit()
    return ActionResponse(
        narration=narration,
        narration_html=render_narrator_html(
            narration,
            list(game_state.last_visible_entities),
            language,
        ),
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

    Raises ``GameNotFoundError`` if the player has no game or the supplied
    ``game_id`` doesn't match — both yield 404 to avoid leaking existence.
    """
    session_row = await repo.sessions.get_latest_web(player_id)
    if session_row is None:
        raise GameNotFoundError(player_id)
    session_id = session_row["id"]
    language = session_language(session_row)
    engine = await resume_session(repo, cfg, session_id, language)
    if engine is None:
        raise GameNotFoundError(player_id)
    game_state, _, _ = engine.assert_running()
    if str(game_state.uuid) != game_id:
        raise GameNotFoundError(player_id)

    return await _act_and_persist(repo, session_id, engine, action, language)
