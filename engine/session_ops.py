"""Shared session-lifecycle helpers used by web-facing game flows.

These helpers keep the recipe for starting / resuming an engine and
persisting state at the end of a turn in one place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cast import _reliability_metrics as reliability_metrics
from config import Config
from engine.factory import create_engine
from engine.session_restore import restore_engine_with_admin_settings
from engine.game_engine import GameEngine
from engine.model_overrides import load_role_overrides
from engine.search_settings import load_search_override
from llm.call_logger import current_session_id, get_and_clear_buffer, reset_buffer
from llm.turn_event_logger import get_and_clear_events, record_turn_event, reset_events

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
    _flush_reliability_snapshot()
    turn_events = get_and_clear_events()
    if turn_events:
        await repo.turn_events.save(
            turn_events,
            session_id=session_id,
            turn_number=turn_number,
            scene_number=game_state.scene_number,
        )


def _flush_reliability_snapshot() -> None:
    """Append the turn's reliability counters to the turn-event buffer.

    Counters are persisted via the existing ``turn_events`` channel
    (no DB migration) — the ``ai_call_logs`` table has only typed
    columns, so the ``turn_events.payload`` JSONB column is the
    natural piggyback target for arbitrary per-turn metering blobs.
    No-op when no counters were recorded this turn so we don't pollute
    the event stream on quiet turns.
    """
    counters = reliability_metrics.snapshot_counters()
    if not counters:
        return
    record_turn_event(
        "reliability_snapshot",
        {"counters": _serialise_counters(counters)},
    )


_CounterMap = dict[tuple[str, str], int]
_CounterRow = dict[str, object]


def _serialise_counters(counters: _CounterMap) -> list[_CounterRow]:
    """Render counter map as a JSON-safe list of records."""
    return [
        {"agent": agent, "event_type": event_type, "count": count}
        for (agent, event_type), count in sorted(counters.items())
    ]


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
    reliability_metrics.reset_counters()


async def begin_session(
    repo: "GameRepository",
    cfg: Config,
    session_id: str,
    language: str,
) -> GameEngine:
    """Bind buffers to the session and build a fresh engine for a new game."""
    _bind_session_buffers(session_id)
    overrides = await load_role_overrides(repo)
    search_override = await load_search_override(repo)
    return create_engine(cfg, language=language, overrides=overrides, search_override=search_override)


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
    return await restore_engine_with_admin_settings(repo, cfg, loaded, language)
