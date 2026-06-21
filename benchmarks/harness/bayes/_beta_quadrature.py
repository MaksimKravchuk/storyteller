"""Deterministic quadrature for ``P(theta_current < theta_baseline)``.

Two Beta posteriors are compared by integrating ``f_baseline * F_current`` over a
uniform grid with the trapezoid rule — pure stdlib, no special-function library,
fully deterministic. ``alpha`` and ``beta`` are always ``>= 1`` here (a uniform
prior plus non-negative counts), so the density is finite on the closed interval.
"""

from __future__ import annotations

import math
import operator

from benchmarks.harness.bayes._types import BetaParams

_GRID_STEPS = 1000


def _log_beta_norm(dist: BetaParams) -> float:
    """Log of ``1 / B(alpha, beta)`` — the Beta density's normalising constant."""
    total = math.lgamma(dist.alpha + dist.beta)
    return total - math.lgamma(dist.alpha) - math.lgamma(dist.beta)


def _beta_pdf(point: float, dist: BetaParams) -> float:
    """Beta density at ``point`` in [0, 1]; closed endpoints handled explicitly."""
    log_norm = _log_beta_norm(dist)
    if point <= 0:
        return math.exp(log_norm) if dist.alpha == 1 else float(0)
    if point >= 1:
        return math.exp(log_norm) if dist.beta == 1 else float(0)
    left = (dist.alpha - 1) * math.log(point)
    right = (dist.beta - 1) * math.log1p(-point)
    return math.exp(log_norm + left + right)


def _densities(dist: BetaParams, step: float) -> list[float]:
    """Beta density sampled on the closed ``[0, 1]`` grid."""
    return [_beta_pdf(index * step, dist) for index in range(_GRID_STEPS + 1)]


def _cumulative_trapezoid(series: list[float], step: float) -> list[float]:
    """Running trapezoid integral of ``series`` — the discretised CDF."""
    running = float(0)
    cumulative = [running]
    for left, right in zip(series, series[1:]):
        running += 0.5 * (left + right) * step
        cumulative.append(running)
    return cumulative


def _trapezoid(series: list[float], step: float) -> float:
    """Composite trapezoid integral of ``series`` over the grid."""
    ends = 0.5 * (series[0] + series[-1])
    return step * (ends + math.fsum(series[1:-1]))


def prob_below(baseline: BetaParams, current: BetaParams) -> float:
    """``P(theta_current < theta_baseline)`` = integral of ``f_base * F_current``."""
    step = 1.0 / _GRID_STEPS
    base_density = _densities(baseline, step)
    current_cdf = _cumulative_trapezoid(_densities(current, step), step)
    products = list(map(operator.mul, base_density, current_cdf))
    integral = _trapezoid(products, step)
    return min(max(integral, float(0)), float(1))
