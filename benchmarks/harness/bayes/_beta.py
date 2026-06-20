"""Per-element Beta-Binomial drill-down over retained judge votes.

Each evidence element is a sequence of YES/NO judge votes — a Binomial. With a
uniform ``Beta(1, 1)`` prior the pass-probability posterior is
``Beta(1 + yes, 1 + no)``. Comparing the current posterior to the baseline
posterior yields ``P(theta_current < theta_baseline)`` — a graded per-element
regression probability that sharpens automatically as the judge panel widens,
with no extra engine iteration. Judge votes are preferred; iteration pass-counts
are the fallback for baselines pinned before tallies were retained.
"""

from __future__ import annotations

from benchmarks.harness.bayes._beta_quadrature import prob_below
from benchmarks.harness.bayes._types import (
    BetaParams,
    ElementInferiority,
    Resolution,
    VoteCounts,
)


def _beta_from(yes: int, total: int) -> BetaParams:
    """Beta posterior from a uniform prior plus ``yes`` successes in ``total`` trials."""
    return BetaParams(alpha=1 + yes, beta=1 + (total - yes))


def _mean_rate(dist: BetaParams) -> float:
    """Posterior mean pass-probability of a Beta(alpha, beta)."""
    return dist.alpha / (dist.alpha + dist.beta)


def _resolution(baseline: VoteCounts, current: VoteCounts) -> tuple[BetaParams, BetaParams, Resolution]:
    """Prefer judge votes; fall back to iteration pass-counts; else a flat prior."""
    if baseline.votes > 0 and current.votes > 0:
        baseline_beta = _beta_from(baseline.yes, baseline.votes)
        current_beta = _beta_from(current.yes, current.votes)
        return baseline_beta, current_beta, "judges"
    if baseline.iterations > 0 and current.iterations > 0:
        baseline_beta = _beta_from(baseline.passes, baseline.iterations)
        current_beta = _beta_from(current.passes, current.iterations)
        return baseline_beta, current_beta, "iterations"
    flat = BetaParams(alpha=1, beta=1)
    return flat, flat, "none"


def element_inferiority(
    element_id: str,
    label: str,
    baseline: VoteCounts,
    current: VoteCounts,
) -> ElementInferiority:
    """Build the per-element Beta-Binomial verdict at the best available resolution."""
    baseline_params, current_params, resolution = _resolution(baseline, current)
    p_regression = prob_below(baseline_params, current_params)
    return ElementInferiority(
        element_id=element_id,
        label=label,
        p_regression=p_regression,
        p_improvement=1 - p_regression,
        baseline_rate=_mean_rate(baseline_params),
        current_rate=_mean_rate(current_params),
        resolution=resolution,
    )
