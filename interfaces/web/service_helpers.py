"""Internal helpers for ``interfaces.web.service``.

Split out to keep the public service module under wemake's
``WPS202 too many module members`` cap.
"""

from __future__ import annotations

from config import Config
from db.repository import GameRepository
from engine.factory import create_engine_from_state
from engine.game_engine import GameEngine
from interfaces.web.schemas import GameSnapshot
from interfaces.web.transcript import build_transcript
from llm.call_logger import get_and_clear_buffer
from llm.turn_event_logger import get_and_clear_events

_DEFAULT_LANGUAGE = "English"


async def persist_engine(
    repo: GameRepository,
    session_id: str,
    engine: GameEngine,
    turn_number: int | None,
) -> None:
    """Save game state and flush any buffered AI call logs."""
    game_state = engine.game_state
    if game_state is None:
        raise RuntimeError("engine.game_state is None — engine did not initialise correctly")
    if engine.knowledge_graph is None:
        raise RuntimeError("engine.knowledge_graph is None — engine did not initialise correctly")
    await repo.save_game_state(
        session_id,
        game_state,
        engine.knowledge_graph,
        engine.event_manager.all_events if engine.event_manager else [],
    )
    ai_logs = get_and_clear_buffer()
    if ai_logs:
        await repo.ai_logs.save(ai_logs, turn_number=turn_number)
    turn_events = get_and_clear_events()
    if turn_events:
        scene_number = game_state.scene_number if game_state else None
        await repo.turn_events.save(
            turn_events,
            session_id=session_id,
            turn_number=turn_number,
            scene_number=scene_number,
        )


def snapshot_from_engine(engine: GameEngine) -> GameSnapshot:
    """Build a ``GameSnapshot`` view from a fully-initialised engine."""
    game_state = engine.game_state
    if game_state is None:
        raise RuntimeError("engine.game_state is None — cannot build snapshot")
    return GameSnapshot(
        game_id=str(game_state.uuid),
        setting=game_state.setting.name,
        transcript=build_transcript(game_state.conversation_log),
        turn_count=game_state.turn_count,
    )


def session_language(session_row: dict) -> str:
    """Extract a language from a session row, defaulting to English."""
    return session_row.get("language") or _DEFAULT_LANGUAGE


async def restore_engine(
    repo: GameRepository,
    cfg: Config,
    session_row: dict,
) -> GameEngine | None:
    """Load saved state for a session and return a restored engine, or None."""
    loaded = await repo.load_game_state(session_row["id"])
    if loaded is None:
        return None
    game_state, kg, events = loaded
    return await create_engine_from_state(
        cfg,
        game_state,
        kg,
        events,
        language=session_language(session_row),
    )
