"""Regression / improvement / noise classifiers for ``benchmarks compare``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

_REGRESSION: Literal["regression"] = "regression"
_IMPROVEMENT: Literal["improvement"] = "improvement"
_NOISE: Literal["noise"] = "noise"

Classification = Literal["regression", "improvement", "noise"]
PassRateClassification = Literal["regression", "improvement", "noise", "-"]


@dataclass(frozen=True)
class PassRatePair:
    """Baseline + current pass-rate counts for one element."""

    label: str
    baseline_passes: int
    baseline_iters: int
    current_passes: int
    current_iters: int


def classify_range(
    baseline_min: int,
    baseline_max: int,
    current_min: int,
    current_max: int,
) -> Classification:
    """Compare two score ranges; non-overlapping is signal, overlap is noise."""
    if current_max < baseline_min:
        return _REGRESSION
    if current_min > baseline_max:
        return _IMPROVEMENT
    return _NOISE


def classify_stdev_overlap(
    baseline_mean: float,
    baseline_stdev: float,
    current_mean: float,
    current_stdev: float,
    *,
    sigma_multiplier: float = 1.0,
) -> Classification:
    """Classify by whether the k-sigma bands around the means overlap.

    Regression: current's upper band sits below baseline's lower band.
    Improvement: current's lower band sits above baseline's upper band.
    Otherwise: bands overlap → noise. This is the primary verdict for
    ``iterations >= 3`` (where stdev is meaningful); ``classify_range`` remains
    the fallback for smaller samples.
    """
    current_upper = current_mean + sigma_multiplier * current_stdev
    current_lower = current_mean - sigma_multiplier * current_stdev
    baseline_upper = baseline_mean + sigma_multiplier * baseline_stdev
    baseline_lower = baseline_mean - sigma_multiplier * baseline_stdev
    if current_upper < baseline_lower:
        return _REGRESSION
    if current_lower > baseline_upper:
        return _IMPROVEMENT
    return _NOISE


def classify_pass_rate(pair: PassRatePair) -> PassRateClassification:
    """Classify a per-element pass-rate delta by whether it crosses the 50% line."""
    # Signal is a crossing of the strict-majority threshold: movements that stay
    # on the same side (e.g. 2/3 → 3/3) are noise — variance cannot flip majority.
    if pair.baseline_iters <= 0 or pair.current_iters <= 0:
        return "-"
    baseline_majority = 2 * pair.baseline_passes > pair.baseline_iters
    current_majority = 2 * pair.current_passes > pair.current_iters
    if baseline_majority and not current_majority:
        return _REGRESSION
    if current_majority and not baseline_majority:
        return _IMPROVEMENT
    return _NOISE
