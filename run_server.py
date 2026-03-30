"""Production entry point — runs the Telegram bot + admin dashboard."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys

from config import load_config
from db.engine import create_async_engine, create_session_factory
from interfaces.admin import AdminServer
from interfaces.telegram_bot import build_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

_ADMIN_PORT = 8080


def _run_migrations() -> None:
    """Apply pending Alembic migrations before starting."""
    logger.info("Running database migrations...")
    proc = subprocess.run(  # noqa: S603,S607
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        logger.error("Migration failed:\n%s", proc.stderr)
        sys.exit(1)
    logger.info("Migrations complete.")


async def main() -> None:
    cfg = load_config()

    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    session_factory = create_session_factory(engine)

    admin = AdminServer(
        session_factory,
        port=_ADMIN_PORT,
        token=os.getenv("ADMIN_TOKEN"),
    )
    await admin.start()

    if cfg.telegram_bot_token:
        bot = build_bot(cfg, session_factory)
        async with bot:
            await bot.initialize()
            await bot.start()
            await bot.updater.start_polling()
            logger.info("Telegram bot polling started.")
            # Run until interrupted
            await asyncio.Event().wait()
            await bot.updater.stop()
            await bot.stop()
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot disabled, admin only.")
        await asyncio.Event().wait()

    await admin.stop()
    await engine.dispose()


if __name__ == "__main__":
    _run_migrations()
    asyncio.run(main())
