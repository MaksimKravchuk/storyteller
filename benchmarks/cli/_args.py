"""Argparse configuration for the benchmarks CLI."""

from __future__ import annotations

import argparse

_DEFAULT_ITERATIONS = 3
_DEFAULT_CALIBRATE_ITERATIONS = 5


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
    _register_pin_parser(sub)
    _register_baselines_parser(sub)
    _register_calibrate_parser(sub)
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


def _register_pin_parser(sub: argparse._SubParsersAction) -> None:
    """Register the ``pin`` subcommand."""
    pin_cmd = sub.add_parser("pin", help="Pin an aggregate as the canonical baseline for a scenario.")
    pin_cmd.add_argument("scenario_id", type=str, help="Scenario id to pin a baseline for.")
    pin_cmd.add_argument(
        "--from",
        dest="from_path",
        type=str,
        required=True,
        help="Path to the aggregate JSON to copy into the baselines directory.",
    )


def _register_baselines_parser(sub: argparse._SubParsersAction) -> None:
    """Register the ``baselines`` subcommand."""
    baselines_cmd = sub.add_parser("baselines", help="Inspect pinned baselines.")
    baselines_sub = baselines_cmd.add_subparsers(dest="baselines_action", required=True)
    baselines_sub.add_parser("list", help="List scenarios that have a pinned baseline.")


def _register_calibrate_parser(sub: argparse._SubParsersAction) -> None:
    """Register the ``calibrate`` subcommand."""
    calibrate_cmd = sub.add_parser(
        "calibrate",
        help="Run N iterations per scenario and write a noise-floor calibration file.",
    )
    calibrate_cmd.add_argument(
        "--scenario",
        action="append",
        default=None,
        help="Scenario id (repeatable). Omit to calibrate every registered scenario.",
    )
    calibrate_cmd.add_argument(
        "--iterations",
        type=_positive_int,
        default=_DEFAULT_CALIBRATE_ITERATIONS,
        help="Iterations per scenario (default {0}).".format(_DEFAULT_CALIBRATE_ITERATIONS),
    )
    calibrate_cmd.add_argument(
        "--judges",
        type=str,
        default=None,
        help="Comma-separated override list of judge aliases / model ids.",
    )
    calibrate_cmd.add_argument(
        "--max-judges",
        type=int,
        default=None,
        help="Cap panel size (defaults to harness-wide maximum).",
    )
