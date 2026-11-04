"""Top-level command dispatcher."""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from benchmarks.cli._args import parse_args
from benchmarks.cli._async_commands import ASYNC_COMMANDS
from benchmarks.cli._sync_commands import SYNC_COMMANDS
from log_scrubbing import LOGURU_DIAGNOSE_ENABLED, scrub_log_record

_UNKNOWN_COMMAND_EXIT_CODE = 2


def _argv_for(argv: list[str] | None) -> list[str]:
    """Pick the argv list to parse, falling back to ``sys.argv``."""
    if argv is None:
        return sys.argv[1:]
    return list(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — dispatch on the parsed subcommand."""
    # CI logs are public: loguru's default diagnose sink would print Config (API keys) in tracebacks.
    logger.configure(
        handlers=[{"sink": sys.stderr, "level": "DEBUG", "diagnose": LOGURU_DIAGNOSE_ENABLED}],
        patcher=scrub_log_record,
    )
    args = parse_args(_argv_for(argv))
    async_handler = ASYNC_COMMANDS.get(args.command)
    if async_handler is not None:
        return asyncio.run(async_handler(args))
    sync_handler = SYNC_COMMANDS.get(args.command)
    if sync_handler is not None:
        return sync_handler(args)
    sys.stderr.write("Unknown command: {0}\n".format(args.command))
    return _UNKNOWN_COMMAND_EXIT_CODE
