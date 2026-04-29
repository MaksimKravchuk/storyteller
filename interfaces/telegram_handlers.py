"""Telegram message handler logic — extracted from telegram_bot."""

from __future__ import annotations

from typing import Any

from loguru import logger

from db.repository import GameRepository
from engine.factory import create_engine_from_state, create_engine_with_db_overrides
from engine.game_engine import GameEngine
from interfaces.telegram_handlers_helpers import recover_from_start_failure, _STATE_IDLE
from formatting.markdown_render import render
from formatting.platform import ClientPlatform
from llm.call_logger import current_session_id, get_and_clear_buffer, reset_buffer
from llm.turn_event_logger import get_and_clear_events, reset_events

_TELEGRAM_PARSE_MODE = "HTML"


def _reset_turn_buffers() -> None:
    """Reset both the AI-call-log buffer and the structured turn-event buffer."""
    reset_buffer()
    reset_events()


async def persist_engine_state(
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


async def start_new_game(engine: Any, repo: Any, session_id: str, update: Any, text: str) -> None:
    """Run start_game and persist. Extracted to keep try-body short."""
    opening = await engine.start_game(text)
    await persist_engine_state(repo, session_id, engine, turn_number=None)
    await repo.sessions.update(session_id, state="playing")
    await update.message.reply_text(
        render(opening, ClientPlatform.TELEGRAM_HTML),
        parse_mode=_TELEGRAM_PARSE_MODE,
    )


async def process_player_action(engine: Any, repo: Any, session_id: str, update: Any, text: str) -> None:
    """Run process_action and persist. Extracted to keep try-body short."""
    response = await engine.process_action(text)
    game_state, _, _ = engine.assert_running()
    await persist_engine_state(repo, session_id, engine, turn_number=game_state.turn_count)
    await update.message.reply_text(
        render(response, ClientPlatform.TELEGRAM_HTML),
        parse_mode=_TELEGRAM_PARSE_MODE,
    )


async def handle_awaiting_setting(ctx: Any, chat_id: int) -> None:
    """Handle the 'awaiting_setting' state: research and start a new game."""
    await ctx.update.message.reply_text(
        "Researching setting and generating opening scene... (this may take a minute)",
    )
    with logger.contextualize(session_id=ctx.session_id):
        current_session_id.set(ctx.session_id)
        _reset_turn_buffers()
        engine = await create_engine_with_db_overrides(ctx.repo, ctx.cfg, language=ctx.language)
        try:
            await start_new_game(engine, ctx.repo, ctx.session_id, ctx.update, ctx.text)
        except Exception:
            await recover_from_start_failure(ctx, chat_id)


async def handle_playing(ctx: Any) -> None:
    """Handle the 'playing' state: load game, process action, persist."""
    loaded = await load_game_or_reset(ctx.repo, ctx.session_id, ctx.update)
    if loaded is None:
        return

    game_state, kg, events = loaded
    engine = await create_engine_from_state(ctx.cfg, game_state, kg, events, language=ctx.language)

    with logger.contextualize(session_id=ctx.session_id):
        current_session_id.set(ctx.session_id)
        _reset_turn_buffers()
        try:
            await process_player_action(engine, ctx.repo, ctx.session_id, ctx.update, ctx.text)
        except Exception:
            logger.exception("Error processing action for session {}", ctx.session_id)
            await ctx.update.message.reply_text("Something went wrong processing your action. Try again.")


async def load_game_or_reset(
    repo: GameRepository,
    session_id: str,
    update: Any,
) -> tuple | None:
    """Load game state; if missing, notify user and reset session."""
    loaded = await repo.load_game_state(session_id)
    if loaded is None:
        await update.message.reply_text("No game found. Send /start to begin.")
        await repo.sessions.update(session_id, state=_STATE_IDLE)
    return loaded
