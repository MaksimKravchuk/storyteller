"""Top-level command dispatcher."""

from __future__ import annotations

import asyncio
import sys

from benchmarks.cli._args import parse_args
from benchmarks.cli._compare import compare_command
from benchmarks.cli._run import run_command

_UNKNOWN_COMMAND_EXIT_CODE = 2


def _argv_for(argv: list[str] | None) -> list[str]:
    """Pick the argv list to parse, falling back to ``sys.argv``."""
    if argv is None:
        return sys.argv[1:]
    return list(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — dispatch on the parsed subcommand."""
    args = parse_args(_argv_for(argv))
    if args.command == "run":
        return asyncio.run(run_command(args))
    if args.command == "compare":
        return compare_command(args)
    sys.stderr.write("Unknown command: {0}\n".format(args.command))
    return _UNKNOWN_COMMAND_EXIT_CODE
