"""Subcommand handler dispatch maps for the benchmarks CLI."""

from __future__ import annotations

import argparse
from types import MappingProxyType
from typing import Any, Callable, Coroutine, Mapping

from benchmarks.cli._baselines import baselines_command
from benchmarks.cli._calibrate import calibrate_command
from benchmarks.cli._compare import compare_command
from benchmarks.cli._pin import pin_command
from benchmarks.cli._reliability_report import reliability_report_command
from benchmarks.cli._run import run_command

SyncHandler = Callable[[argparse.Namespace], int]
AsyncHandler = Callable[[argparse.Namespace], Coroutine[Any, Any, int]]


SYNC_COMMANDS: Mapping[str, SyncHandler] = MappingProxyType(
    {
        "compare": compare_command,
        "pin": pin_command,
        "baselines": baselines_command,
        "reliability-report": reliability_report_command,
    },
)

ASYNC_COMMANDS: Mapping[str, AsyncHandler] = MappingProxyType(
    {
        "run": run_command,
        "calibrate": calibrate_command,
    },
)
