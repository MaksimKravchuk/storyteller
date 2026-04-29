"""Engine-side persistence helper shared by the telegram and web interfaces.

A turn finishes by saving the engine's state, draining any AI-call logs
buffered for the turn, and flushing structured turn events. Both
interfaces ran a byte-equivalent copy of this routine; this module owns
the single source of truth.
"""

from __future__ import annotations

from db.repository import GameRepository
from engine.game_engine import GameEngine
from llm.call_logger import get_and_clear_buffer
from llm.turn_event_logger import get_and_clear_events


async def persist_engine(
    repo: GameRepository,
    session_id: str,
    engine: GameEngine,
    turn_number: int | None,
) -> None:
    """Save game state and flush any buffered AI call logs."""
    game_state, knowledge_graph, event_manager = engine.assert_running()
    await repo.save_game_state(session_id, game_state, knowledge_graph, event_manager.all_events)
    ai_logs = get_and_clear_buffer()
    if ai_logs:
        await repo.ai_logs.save(ai_logs, turn_number=turn_number)
    turn_events = get_and_clear_events()
    if turn_events:
        await repo.turn_events.save(
            turn_events,
            session_id=session_id,
            turn_number=turn_number,
            scene_number=game_state.scene_number,
        )
