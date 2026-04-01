"""Production entry point — runs the Telegram bot + admin dashboard."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import types

from loguru import logger

from config import Config, load_config
from db.engine import create_async_engine, create_session_factory
from interfaces.admin import AdminServer
from interfaces.telegram_bot import build_bot

_ADMIN_PORT = 8080
_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan> | "
    "session=<yellow>{extra[session_id]}</yellow> | "
    "{message}"
)


class _InterceptHandler(logging.Handler):
    """Route stdlib logging (telegram, aiohttp, …) through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame: types.FrameType | None = sys._getframe(6)  # noqa: WPS437
        depth = 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        log_message = record.getMessage()
        try:
            logger.opt(depth=depth, exception=record.exc_info).log(level, log_message)
        except Exception as exc:
            sys.stderr.write(
                f"_InterceptHandler: loguru failed ({type(exc).__name__}: {exc}). "
                f"Original: [{record.levelname}] {record.name}: {record.getMessage()}\n"
            )


logger.configure(
    handlers=[{"sink": sys.stdout, "format": _LOG_FORMAT, "level": "DEBUG", "colorize": True}],
    extra={"session_id": "-"},
)
logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)


def _run_migrations() -> None:
    """Apply pending Alembic migrations before starting."""
    logger.info("Running database migrations...")
    proc = subprocess.run(  # noqa: S603,S607
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        logger.error(
            "Migration failed (exit code {}).\nstdout:\n{}\nstderr:\n{}",
            proc.returncode,
            proc.stdout or "(empty)",
            proc.stderr or "(empty)",
        )
        sys.exit(1)
    logger.info("Migrations complete.")


async def _run_telegram_bot(cfg: Config, session_factory) -> None:
    """Initialize, start, and poll the Telegram bot until shutdown."""
    bot = build_bot(cfg, session_factory)
    async with bot:
        await bot.initialize()
        await bot.start()
        await bot.updater.start_polling()
        logger.info("Telegram bot polling started.")
        await asyncio.Event().wait()


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

    try:  # noqa: WPS501
        if cfg.telegram_bot_token:
            await _run_telegram_bot(cfg, session_factory)
        else:
            logger.warning("TELEGRAM_BOT_TOKEN not set — bot disabled, admin only.")
            await asyncio.Event().wait()
    finally:
        await admin.stop()
        await engine.dispose()


if __name__ == "__main__":
    _run_migrations()
    asyncio.run(main())
