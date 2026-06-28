"""The asynchronous subcommand dispatch map for the benchmarks CLI."""

from __future__ import annotations

import argparse
from types import MappingProxyType
from typing import Any, Callable, Coroutine, Mapping

from benchmarks.cli._calibrate import calibrate_command
from benchmarks.cli._golden_update import golden_update_command
from benchmarks.cli._run import run_command

AsyncHandler = Callable[[argparse.Namespace], Coroutine[Any, Any, int]]

ASYNC_COMMANDS: Mapping[str, AsyncHandler] = MappingProxyType(
    {
        "run": run_command,
        "calibrate": calibrate_command,
        "golden-update": golden_update_command,
    },
)
