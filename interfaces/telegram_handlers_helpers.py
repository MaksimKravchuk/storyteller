"""Small helpers kept separate from ``telegram_handlers`` to respect module-member limits."""

from __future__ import annotations

from typing import Any

from loguru import logger

_STATE_IDLE = "idle"


async def recover_from_start_failure(ctx: Any, chat_id: int) -> None:
    """Roll back the repo and notify the user after a failed new-game start."""
    logger.exception("Failed to start game for chat {}", chat_id)
    await ctx.repo.rollback()
    await ctx.update.message.reply_text("Something went wrong. Try /start again.")
    await ctx.repo.sessions.update(ctx.session_id, state=_STATE_IDLE)
