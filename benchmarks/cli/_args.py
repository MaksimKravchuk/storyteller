"""Argparse configuration for the benchmarks CLI."""

from __future__ import annotations

import argparse


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the ``benchmarks`` CLI invocation."""
    parser = argparse.ArgumentParser(
        prog="benchmarks",
        description="Run deterministic narration benchmarks for the Storyteller engine.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _register_run_parser(sub)
    _register_compare_parser(sub)
    return parser.parse_args(argv)


def _register_run_parser(sub: argparse._SubParsersAction) -> None:
    """Register the ``run`` subcommand."""
    run_cmd = sub.add_parser("run", help="Run one or more benchmark scenarios.")
    run_cmd.add_argument(
        "--scenario",
        action="append",
        default=None,
        help="Scenario id (repeatable). Omit to run every registered scenario.",
    )
    run_cmd.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of iterations per scenario (default 1).",
    )
    run_cmd.add_argument(
        "--judges",
        type=str,
        default=None,
        help="Comma-separated override list of judge aliases / model ids.",
    )
    run_cmd.add_argument(
        "--max-judges",
        type=int,
        default=None,
        help="Cap panel size (defaults to harness-wide maximum).",
    )


def _register_compare_parser(sub: argparse._SubParsersAction) -> None:
    """Register the ``compare`` subcommand."""
    compare_cmd = sub.add_parser("compare", help="Diff two archived JSON reports.")
    compare_cmd.add_argument("baseline", type=str, help="Path to the baseline JSON report.")
    compare_cmd.add_argument("current", type=str, help="Path to the new JSON report.")
