"""Argparse configuration for the benchmarks CLI."""

from __future__ import annotations

import argparse

from benchmarks.cli._args_subcommands import register_extra_subcommands

_DEFAULT_ITERATIONS = 3


def _positive_int(raw: str) -> int:
    """Argparse type for ``--iterations``: reject zero and negative values."""
    try:
        candidate = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("iterations must be an integer, got {0!r}".format(raw)) from exc
    if candidate < 1:
        raise argparse.ArgumentTypeError("iterations must be >= 1, got {0}".format(candidate))
    return candidate


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the ``benchmarks`` CLI invocation."""
    parser = argparse.ArgumentParser(
        prog="benchmarks",
        description="Run deterministic narration benchmarks for the Storyteller engine.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _register_run_parser(sub)
    _register_compare_parser(sub)
    _register_bayes_report_parser(sub)
    register_extra_subcommands(sub)
    return parser.parse_args(argv)


def _non_negative_float(raw: str) -> float:
    """Argparse type for ``--rope``: reject negative widths."""
    try:
        candidate = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("rope must be a number, got {0!r}".format(raw)) from exc
    if candidate < 0:
        raise argparse.ArgumentTypeError("rope must be >= 0, got {0}".format(candidate))
    return candidate


def _register_bayes_report_parser(sub: argparse._SubParsersAction) -> None:
    """Register the ``bayes-report`` subcommand."""
    bayes_cmd = sub.add_parser(
        "bayes-report",
        help="Graded Bayesian verdicts + portfolio bias vs pinned baselines (offline).",
    )
    bayes_cmd.add_argument(
        "results",
        type=str,
        help="Directory of current *_aggregate.json files to score against pinned baselines.",
    )
    bayes_cmd.add_argument(
        "--rope",
        type=_non_negative_float,
        default=None,
        help="Region-of-practical-equivalence half-width in score points (default 0.5).",
    )


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
        type=_positive_int,
        default=_DEFAULT_ITERATIONS,
        help="Number of iterations per scenario (default {0}).".format(_DEFAULT_ITERATIONS),
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
    run_cmd.add_argument(
        "--no-compare",
        action="store_true",
        help="Skip the auto-compare against pinned baselines (always exits 0).",
    )
    run_cmd.add_argument(
        "--update-baselines-on-improvement",
        action="store_true",
        help="Ratchet pinned baseline forward when improvement > 2 * noise_floor_stdev.",
    )


def _register_compare_parser(sub: argparse._SubParsersAction) -> None:
    """Register the ``compare`` subcommand."""
    compare_cmd = sub.add_parser("compare", help="Diff two archived aggregate reports.")
    compare_cmd.add_argument("baseline", type=str, help="Path to the baseline aggregate JSON report.")
    compare_cmd.add_argument("current", type=str, help="Path to the new aggregate JSON report.")
