"""Argparse subcommand registrations beyond ``run`` and ``compare``."""

from __future__ import annotations

import argparse

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


def register_extra_subcommands(sub: argparse._SubParsersAction) -> None:
    """Register pin, baselines, calibrate, reliability-report, narration-diff subcommands."""
    _register_pin_parser(sub)
    _register_baselines_parser(sub)
    _register_calibrate_parser(sub)
    _register_reliability_report_parser(sub)
    _register_narration_diff_parser(sub)


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
    calibrate_cmd.add_argument(
        "--compare-to-baselines",
        action="store_true",
        default=False,
        help=(
            "After calibrating, compare new stdev values against the previous "
            ".calibration.json and print a drift table. Exits with code 1 when "
            "any scenario drifts >=50%%."
        ),
    )


def _register_reliability_report_parser(sub: argparse._SubParsersAction) -> None:
    """Register the ``reliability-report`` subcommand."""
    reliability_cmd = sub.add_parser(
        "reliability-report",
        help="Tabulate silent fallbacks + validation retries across per-iteration archives.",
    )
    reliability_cmd.add_argument(
        "path",
        type=str,
        help="Per-iteration JSON archive file or directory containing one or more.",
    )


def _register_narration_diff_parser(sub: argparse._SubParsersAction) -> None:
    """Register the ``narration-diff`` subcommand."""
    narration_cmd = sub.add_parser(
        "narration-diff",
        help="Render a markdown narration diff between two result directories.",
    )
    narration_cmd.add_argument(
        "previous",
        type=str,
        help="Directory of previous-version per-iteration result JSONs.",
    )
    narration_cmd.add_argument(
        "current",
        type=str,
        help="Directory of current-version per-iteration result JSONs.",
    )
