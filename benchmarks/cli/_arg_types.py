"""Shared argparse ``type=`` validators for the benchmarks CLI."""

from __future__ import annotations

import argparse


def positive_int(raw: str) -> int:
    """Argparse type for ``--iterations``: reject zero and negative values."""
    try:
        candidate = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("iterations must be an integer, got {0!r}".format(raw)) from exc
    if candidate < 1:
        raise argparse.ArgumentTypeError("iterations must be >= 1, got {0}".format(candidate))
    return candidate


def non_negative_float(raw: str) -> float:
    """Argparse type for ``--rope``: reject negative widths."""
    try:
        candidate = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("rope must be a number, got {0!r}".format(raw)) from exc
    if candidate < 0:
        raise argparse.ArgumentTypeError("rope must be >= 0, got {0}".format(candidate))
    return candidate
