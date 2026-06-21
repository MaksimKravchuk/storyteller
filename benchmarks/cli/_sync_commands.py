"""The synchronous subcommand dispatch map for the benchmarks CLI."""

from __future__ import annotations

import argparse
from types import MappingProxyType
from typing import Callable, Mapping

from benchmarks.cli._baselines import baselines_command
from benchmarks.cli._bayes_report import bayes_report_command
from benchmarks.cli._compare import compare_command
from benchmarks.cli._narration_diff import narration_diff_command
from benchmarks.cli._pin import pin_command
from benchmarks.cli._pr_comment import pr_comment_command
from benchmarks.cli._reliability_report import reliability_report_command

SyncHandler = Callable[[argparse.Namespace], int]

SYNC_COMMANDS: Mapping[str, SyncHandler] = MappingProxyType(
    {
        "compare": compare_command,
        "pin": pin_command,
        "baselines": baselines_command,
        "reliability-report": reliability_report_command,
        "narration-diff": narration_diff_command,
        "bayes-report": bayes_report_command,
        "pr-comment": pr_comment_command,
    },
)
