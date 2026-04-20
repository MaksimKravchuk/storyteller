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
