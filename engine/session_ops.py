"""Shared session-lifecycle helpers used by both web and telegram interfaces.

Each interface used to inline the same recipe for starting / resuming an
engine and for persisting state at the end of a turn. These helpers lift
that recipe into one place so the interface modules stay thin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config import Config
from engine.factory import create_engine, create_engine_from_state
from engine.game_engine import GameEngine
from engine.model_overrides import load_role_overrides
from llm.call_logger import current_session_id, get_and_clear_buffer, reset_buffer
from llm.turn_event_logger import get_and_clear_events, reset_events

if TYPE_CHECKING:
    from db.repository import GameRepository


async def persist_engine_state(
    repo: "GameRepository",
    session_id: str,
    engine: GameEngine,
    turn_number: int | None,
    user_id: str | None = None,
) -> None:
    """Save game state and flush any buffered AI call logs."""
    game_state, knowledge_graph, event_manager = engine.assert_running()
    await repo.save_game_state(session_id, game_state, knowledge_graph, event_manager.all_events)
    ai_logs = get_and_clear_buffer()
    if ai_logs:
        await repo.ai_logs.save(
            ai_logs,
            turn_number=turn_number,
            user_id=user_id,
            game_state_id=_game_state_id(game_state),
        )
    turn_events = get_and_clear_events()
    if turn_events:
        await repo.turn_events.save(
            turn_events,
            session_id=session_id,
            turn_number=turn_number,
            scene_number=game_state.scene_number,
        )


def _game_state_id(game_state: object) -> str | None:
    """Return a string game-state UUID when the runtime state exposes one."""
    raw_uuid = getattr(game_state, "uuid", None)
    if raw_uuid is None:
        return None
    return str(raw_uuid)


def _bind_session_buffers(session_id: str) -> None:
    """Tag the AI call/turn-event buffers with ``session_id`` for this turn."""
    current_session_id.set(session_id)
    reset_buffer()
    reset_events()


async def begin_session(
    repo: "GameRepository",
    cfg: Config,
    session_id: str,
    language: str,
) -> GameEngine:
    """Bind buffers to the session and build a fresh engine for a new game."""
    _bind_session_buffers(session_id)
    overrides = await load_role_overrides(repo)
    return create_engine(cfg, language=language, overrides=overrides)


async def resume_session(
    repo: "GameRepository",
    cfg: Config,
    session_id: str,
    language: str = "English",
) -> GameEngine | None:
    """Bind buffers and restore an engine from saved state, or ``None`` if missing."""
    _bind_session_buffers(session_id)
    loaded = await repo.load_game_state(session_id)
    if loaded is None:
        return None
    game_state, knowledge_graph, events = loaded
    return await create_engine_from_state(
        cfg,
        game_state,
        knowledge_graph,
        events,
        language=language,
    )
