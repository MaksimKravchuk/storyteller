"""Business logic for the web interface.

Thin layer between FastAPI routes and the underlying engine/repository.
Keeps route handlers free of engine wiring so they can be trivially tested
via ``app.dependency_overrides``.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from config import Config
from db.repository import GameRepository
from engine.session_ops import begin_session, resume_session
from interfaces.web import beta_policy, player_gestures, playbill, quota_locks
from interfaces.web.errors import (
    GameNotFoundError,
    GameStartFailedError,
    GameStartUnavailableError,
    is_provider_auth_error,
)
from interfaces.web.runtime import ActionPersistence, StartPersistence
from interfaces.web.schemas import (
    ActionRequest,
    ActionResponse,
    CharacterCreationInput,
    GameSnapshot,
)
from interfaces.web.service_helpers import (
    StartGameParams,
    owned_session_context,
    restore_engine,
    session_language,
    snapshot_from_engine,
)
from models.player_character_input import PlayerCharacterInput

_STATE_PLAYING = "playing"
BetaAccessDeniedError = beta_policy.BetaAccessDeniedError


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


async def _mark_session_playing(repo: GameRepository, session_id: str, language: str) -> None:
    """Mark the new web session playable before returning to the client."""
    await repo.sessions.update(session_id, state=_STATE_PLAYING, language=language)
    await repo.commit()


async def _prepare_started_engine(
    repo: GameRepository,
    cfg: Config,
    start_request: StartGameParams,
):
    """Run beta checks, create a session, and return its engine."""
    policy = beta_policy.BetaPolicy(repo, cfg)
    await policy.ensure_open()
    await policy.ensure_active_game_quota(start_request.player_id, start_request.plan)
    session_row = await repo.sessions.create_web(start_request.player_id)
    session_id = session_row["id"]
    engine = await begin_session(repo, cfg, session_id, start_request.language)
    return session_id, engine


async def start_game_for_player(
    repo: GameRepository,
    cfg: Config,
    start_request: StartGameParams,
) -> GameSnapshot:
    """Create a fresh session for this web player and return the opening snapshot."""
    async with quota_locks.player_lock(start_request.player_id):
        session_id, engine = await _prepare_started_engine(repo, cfg, start_request)
        try:
            await StartPersistence(
                repo=repo,
                session_id=session_id,
                user_id=start_request.player_id,
                engine=engine,
                setting=start_request.setting,
                character=_to_engine_character(start_request.character),
            ).run()
        except Exception as exc:
            logger.exception("Failed to start web game for player {}", start_request.player_id)
            await repo.rollback()
            if is_provider_auth_error(exc):
                raise GameStartUnavailableError("LLM provider credentials rejected game start") from exc
            raise GameStartFailedError("Game start failed at runtime") from exc
        await playbill.save_playbill(repo, session_id, engine.assert_running()[0])
        await _mark_session_playing(repo, session_id, start_request.language)
        return snapshot_from_engine(engine, start_request.language)


async def _act_and_persist(*runtime_args: Any, user_id: str | None = None) -> ActionResponse:
    """Run a player action through the engine and persist the new state."""
    return await ActionPersistence(
        repo=runtime_args[0],
        session_id=runtime_args[1],
        engine=runtime_args[2],
        action=runtime_args[3],
        language=runtime_args[4],
        user_id=user_id,
    ).run()


async def process_turn_for_player(
    repo: GameRepository,
    cfg: Config,
    player_id: Any,
    game_id: str,
    request: ActionRequest,
) -> ActionResponse:
    """Process a player turn on an existing game.

    ``request`` carries exactly one of a free-text ``action`` or a
    structured ``gesture`` (enforced by :class:`ActionRequest`); a gesture
    is resolved against current state and composed into the session-language
    phrase before running the unchanged turn pipeline.

    Raises ``GameNotFoundError`` if the player has no game or the supplied
    ``game_id`` doesn't match — both yield 404 to avoid leaking existence.
    """
    player_identifier = player_id if isinstance(player_id, str) else str(player_id.player_id)
    async with quota_locks.player_lock(player_identifier):
        await beta_policy.BetaPolicy(repo, cfg).ensure_open()
        await beta_policy.BetaPolicy(repo, cfg).ensure_turn_quota(
            player_identifier,
            "friend_beta" if isinstance(player_id, str) else str(player_id.plan),
        )
        session_id, language = await owned_session_context(repo, player_identifier, game_id)
        engine = await resume_session(repo, cfg, session_id, language)
        if engine is None:
            raise GameNotFoundError(player_identifier)

        if request.gesture is None:
            # ActionRequest guarantees a non-blank action whenever no gesture is set.
            phrase = request.action or ""
        else:
            phrase = player_gestures.compose_player_gesture(engine.assert_running()[0], language, request.gesture)

        return await ActionPersistence(
            repo=repo,
            session_id=session_id,
            engine=engine,
            action=phrase,
            language=language,
            user_id=player_identifier,
        ).run()
