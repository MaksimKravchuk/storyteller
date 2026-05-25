"""Implementation of the ``benchmarks baselines`` subcommand."""

from __future__ import annotations

import argparse
import sys

from benchmarks.harness import baselines


def _write(line: str) -> None:
    sys.stdout.write("{0}\n".format(line))


def _list_baselines() -> int:
    """Render the pinned baseline list — one scenario id per line."""
    pinned = baselines.list_baselines()
    if not pinned:
        _write("(no baselines pinned)")
        return 0
    for scenario_id in pinned:
        _write(scenario_id)
    return 0


def baselines_command(args: argparse.Namespace) -> int:
    """Execute the ``baselines`` subcommand."""
    if args.baselines_action == "list":
        return _list_baselines()
    sys.stderr.write("Unknown baselines action: {0}\n".format(args.baselines_action))
    return 2
