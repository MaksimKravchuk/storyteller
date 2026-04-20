"""Argparse configuration for the benchmarks CLI."""

from __future__ import annotations

import argparse

_DEFAULT_ITERATIONS = 3
_QUICK_ITERATIONS = 1


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
    iter_group = run_cmd.add_mutually_exclusive_group()
    iter_group.add_argument(
        "--iterations",
        type=int,
        default=_DEFAULT_ITERATIONS,
        help="Number of iterations per scenario (default {0}).".format(_DEFAULT_ITERATIONS),
    )
    iter_group.add_argument(
        "--quick",
        action="store_true",
        help="Run a single iteration per scenario (smoke-run shorthand for --iterations 1).",
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
    compare_cmd = sub.add_parser("compare", help="Diff two archived aggregate reports.")
    compare_cmd.add_argument("baseline", type=str, help="Path to the baseline aggregate JSON report.")
    compare_cmd.add_argument("current", type=str, help="Path to the new aggregate JSON report.")


def resolve_iterations(args: argparse.Namespace) -> int:
    """Resolve --quick/--iterations into the effective iteration count."""
    if getattr(args, "quick", False):
        return _QUICK_ITERATIONS
    return int(args.iterations)
