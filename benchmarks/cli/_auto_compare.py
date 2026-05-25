"""Automatic per-scenario regression check against pinned baselines.

This is the runtime gate invoked by ``benchmarks run`` after aggregates are
finalised. Each scenario is compared against its pinned baseline (when one
exists); regressions surface as a non-zero exit code from the ``run`` command.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from benchmarks.cli._compare_classify import (
    Classification,
    classify_range,
    classify_stdev_overlap,
)
from benchmarks.harness import baselines
from benchmarks.harness.types._aggregates import PinnedBaseline, ScenarioAggregate

VerdictClassification = Literal["regression", "improvement", "noise", "no_baseline"]

_MIN_ITERATIONS_FOR_STDEV = 3
_RATCHET_STDEV_MULTIPLIER = 2.0


@dataclass(frozen=True)
class Verdict:
    """Result of comparing one scenario's new aggregate to its pinned baseline."""

    scenario_id: str
    classification: VerdictClassification
    baseline_mean: float
    current_mean: float
    delta_vs_noise_floor: float


def _classify(baseline: PinnedBaseline, current: ScenarioAggregate) -> Classification:
    """Pick the verdict rule based on sample size; stdev for N>=3 else range."""
    aggregate = baseline.aggregate
    if current.iterations >= _MIN_ITERATIONS_FOR_STDEV and aggregate.iterations >= _MIN_ITERATIONS_FOR_STDEV:
        return classify_stdev_overlap(
            aggregate.mean_awarded,
            aggregate.stdev_awarded,
            current.mean_awarded,
            current.stdev_awarded,
        )
    return classify_range(
        aggregate.min_awarded,
        aggregate.max_awarded,
        current.min_awarded,
        current.max_awarded,
    )


def _delta_vs_noise(current: ScenarioAggregate, baseline: PinnedBaseline) -> float:
    """Return ``(current.mean - baseline.mean) / noise_floor_stdev`` (0 on stdev==0)."""
    noise = baseline.noise_floor_stdev
    if noise <= 0:
        return float(0)
    return (current.mean_awarded - baseline.aggregate.mean_awarded) / noise


def _verdict_for(current: ScenarioAggregate) -> Verdict:
    """Build a :class:`Verdict` for ``current`` against its pinned baseline."""
    baseline = baselines.read_baseline(current.scenario_id)
    if baseline is None:
        return Verdict(
            scenario_id=current.scenario_id,
            classification="no_baseline",
            baseline_mean=float(0),
            current_mean=current.mean_awarded,
            delta_vs_noise_floor=float(0),
        )
    return Verdict(
        scenario_id=current.scenario_id,
        classification=_classify(baseline, current),
        baseline_mean=baseline.aggregate.mean_awarded,
        current_mean=current.mean_awarded,
        delta_vs_noise_floor=_delta_vs_noise(current, baseline),
    )


def evaluate(aggregates: list[ScenarioAggregate]) -> list[Verdict]:
    """Compute one :class:`Verdict` per aggregate, in input order."""
    return [_verdict_for(aggregate) for aggregate in aggregates]


def any_regression(verdicts: list[Verdict]) -> bool:
    """Return ``True`` when at least one verdict is a regression."""
    return any(verdict.classification == "regression" for verdict in verdicts)


def should_ratchet(
    verdict: Verdict,
    baseline: PinnedBaseline,
    current: ScenarioAggregate,
) -> bool:
    """Predicate for ``--update-baselines-on-improvement``.

    Ratchet **only** when the improvement is statistically robust:
    ``current.mean - baseline.mean > 2 * noise_floor_stdev``. The strict
    multiplier of 2 (not 1) guards against accidental drift when temperature
    is not yet pinned in the engine.
    """
    if verdict.classification != "improvement":
        return False
    noise = baseline.noise_floor_stdev
    if noise <= 0:
        return False
    delta = current.mean_awarded - baseline.aggregate.mean_awarded
    return delta > _RATCHET_STDEV_MULTIPLIER * noise
