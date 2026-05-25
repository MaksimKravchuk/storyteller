"""Top-level command dispatcher."""

from __future__ import annotations

import argparse
import asyncio
import sys
from types import MappingProxyType
from typing import Any, Callable, Coroutine, Mapping

from benchmarks.cli._args import parse_args
from benchmarks.cli._baselines import baselines_command
from benchmarks.cli._calibrate import calibrate_command
from benchmarks.cli._compare import compare_command
from benchmarks.cli._pin import pin_command
from benchmarks.cli._run import run_command

SyncHandler = Callable[[argparse.Namespace], int]
AsyncHandler = Callable[[argparse.Namespace], Coroutine[Any, Any, int]]

_UNKNOWN_COMMAND_EXIT_CODE = 2


def _argv_for(argv: list[str] | None) -> list[str]:
    """Pick the argv list to parse, falling back to ``sys.argv``."""
    if argv is None:
        return sys.argv[1:]
    return list(argv)


_SYNC_COMMANDS: Mapping[str, SyncHandler] = MappingProxyType(
    {
        "compare": compare_command,
        "pin": pin_command,
        "baselines": baselines_command,
    },
)

_ASYNC_COMMANDS: Mapping[str, AsyncHandler] = MappingProxyType(
    {
        "run": run_command,
        "calibrate": calibrate_command,
    },
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — dispatch on the parsed subcommand."""
    args = parse_args(_argv_for(argv))
    async_handler = _ASYNC_COMMANDS.get(args.command)
    if async_handler is not None:
        return asyncio.run(async_handler(args))
    sync_handler = _SYNC_COMMANDS.get(args.command)
    if sync_handler is not None:
        return sync_handler(args)
    sys.stderr.write("Unknown command: {0}\n".format(args.command))
    return _UNKNOWN_COMMAND_EXIT_CODE
