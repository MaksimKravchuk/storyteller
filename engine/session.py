"""Engine-side session bootstraps shared by the telegram and web interfaces.

Both interfaces wrap the engine in the same pre-turn ritual: pin the
session id on the AI-call logger, drain the per-turn buffers, then build
or restore the engine. The two functions here own that ritual; callers
keep their interface-specific glue (UI replies, session row updates,
"not found" handling).

The :func:`engine.persistence.persist_engine` helper closes the loop
after the engine has run.
"""

from __future__ import annotations

from config import Config
from db.repository import GameRepository
from engine.factory import create_engine, create_engine_from_state
from engine.game_engine import GameEngine
from engine.model_overrides import load_role_overrides
from llm.call_logger import current_session_id, reset_buffer
from llm.turn_event_logger import reset_events


async def begin_session(
    repo: GameRepository,
    cfg: Config,
    session_id: str,
    language: str,
) -> GameEngine:
    """Wire a fresh engine ready to call :meth:`GameEngine.start_game`.

    Pins ``session_id`` on the AI-call logger, drains the per-turn
    buffers, and builds an engine with any DB-stored role overrides
    layered on top of the environment defaults.
    """
    current_session_id.set(session_id)
    reset_buffer()
    reset_events()
    overrides = await load_role_overrides(repo)
    return create_engine(cfg, language=language, overrides=overrides)


async def resume_session(
    repo: GameRepository,
    cfg: Config,
    session_id: str,
    language: str,
) -> GameEngine | None:
    """Restore a saved engine from previously persisted state.

    Returns ``None`` when no game state is recorded for ``session_id``;
    callers decide whether to surface a 404, reset the session, or
    something else. Buffers and the session-id context are only touched
    after a successful load so a missing-game probe does not pollute the
    AI-call log of an unrelated turn.
    """
    loaded = await repo.load_game_state(session_id)
    if loaded is None:
        return None
    current_session_id.set(session_id)
    reset_buffer()
    reset_events()
    game_state, knowledge_graph, events = loaded
    return await create_engine_from_state(
        cfg,
        game_state,
        knowledge_graph,
        events,
        language=language,
    )
