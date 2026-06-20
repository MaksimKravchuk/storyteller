"""Conjugate Normal model over scenario totals — the headline delta posterior.

Each scenario total is treated as a draw from ``Normal(mu, sigma**2)`` where
``sigma`` is the calibrated run-to-run noise floor (pinned on every baseline).
With a flat prior on the mean, the posterior over a scenario's true mean is
``Normal(observed_mean, sigma**2 / iterations)``, so the delta between the
current and baseline means is itself Normal. This works from a single current
iteration because the baseline supplies the noise scale — there is no need to
re-run the engine to estimate variance.
"""

from __future__ import annotations

import math

from benchmarks.harness.bayes._types import DeltaPosterior, Sample

_SQRT2 = math.sqrt(2)
_CI_Z_SCORE = 1.959963984540054  # two-sided 95% normal quantile


def normal_cdf(point: float, mean: float, stdev: float) -> float:
    """Return ``P(X <= point)`` for ``X ~ Normal(mean, stdev**2)``.

    A zero (or negative) ``stdev`` collapses to a step function at ``mean``.
    """
    if stdev <= 0:
        return float(point >= mean)
    z_score = (point - mean) / (stdev * _SQRT2)
    return 0.5 * (1 + math.erf(z_score))


def _delta_stdev(noise_floor_stdev: float, baseline: Sample, current: Sample) -> float:
    """Standard error of the (current - baseline) mean under the shared noise floor."""
    if noise_floor_stdev <= 0:
        return float(0)
    if baseline.iterations <= 0 or current.iterations <= 0:
        return float(0)
    inverse_iters = 1 / baseline.iterations + 1 / current.iterations
    variance = noise_floor_stdev**2 * inverse_iters
    return math.sqrt(variance)


def _posterior_from_moments(delta_mean: float, delta_stdev: float, rope: float) -> DeltaPosterior:
    """Assemble a :class:`DeltaPosterior` from a Normal delta and a ROPE."""
    p_regression = normal_cdf(-rope, delta_mean, delta_stdev)
    p_improvement = 1 - normal_cdf(rope, delta_mean, delta_stdev)
    return DeltaPosterior(
        delta_mean=delta_mean,
        delta_stdev=delta_stdev,
        p_regression=p_regression,
        p_improvement=p_improvement,
        p_equivalent=max(float(0), 1 - p_regression - p_improvement),
        ci_low=delta_mean - _CI_Z_SCORE * delta_stdev,
        ci_high=delta_mean + _CI_Z_SCORE * delta_stdev,
        rope=rope,
    )


def scenario_delta_posterior(
    baseline: Sample,
    current: Sample,
    *,
    noise_floor_stdev: float,
    rope: float,
) -> DeltaPosterior:
    """Posterior over ``current.mean - baseline.mean`` under the shared noise floor."""
    delta_mean = current.mean - baseline.mean
    delta_stdev = _delta_stdev(noise_floor_stdev, baseline, current)
    return _posterior_from_moments(delta_mean, delta_stdev, rope)


def pool_deltas(deltas: list[DeltaPosterior], *, rope: float) -> DeltaPosterior:
    """Sum independent scenario deltas into one portfolio posterior.

    The summed delta is the expected total score change across the whole suite;
    its mass below ``-rope`` is the probability the change systematically lowered
    scores — the signal no single noisy scenario can show on its own.
    """
    delta_mean = math.fsum(delta.delta_mean for delta in deltas)
    delta_variance = math.fsum(delta.delta_stdev**2 for delta in deltas)
    return _posterior_from_moments(delta_mean, math.sqrt(delta_variance), rope)
