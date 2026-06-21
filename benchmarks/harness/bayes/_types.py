"""Result dataclasses for the Bayesian benchmark-comparison layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Resolution of the per-element Beta-Binomial: judge votes (k_yes / n_votes)
# carry far more trials than iteration pass-counts, so a wider panel tightens
# the posterior without any extra engine run.
Resolution = Literal["judges", "iterations", "none"]


@dataclass(frozen=True)
class Sample:
    """One side's total-score summary: an observed mean over N iterations."""

    mean: float
    iterations: int


@dataclass(frozen=True)
class BetaParams:
    """Beta posterior shape parameters for one element's pass-probability."""

    alpha: float
    beta: float


@dataclass(frozen=True)
class VoteCounts:
    """One side's per-element tallies: judge YES/total and iteration passes/total."""

    yes: int
    votes: int
    passes: int
    iterations: int


@dataclass(frozen=True)
class DeltaPosterior:
    """Posterior over a score delta (current minus baseline).

    ``p_regression`` / ``p_improvement`` are the posterior masses below
    ``-rope`` and above ``+rope``; ``p_equivalent`` is the mass inside the
    region of practical equivalence. The three sum to 1.
    """

    delta_mean: float
    delta_stdev: float
    p_regression: float
    p_improvement: float
    p_equivalent: float
    ci_low: float
    ci_high: float
    rope: float


@dataclass(frozen=True)
class ElementInferiority:
    """Per-element posterior that the current pass-probability moved.

    ``p_regression`` is ``P(theta_current < theta_baseline)`` under independent
    Beta posteriors; ``p_improvement`` is its complement. ``resolution`` records
    whether judge votes or iteration pass-counts fed the Beta parameters.
    """

    element_id: str
    label: str
    p_regression: float
    p_improvement: float
    baseline_rate: float
    current_rate: float
    resolution: Resolution


@dataclass(frozen=True)
class ScenarioVerdict:
    """Bayesian verdict for one scenario: the total delta plus element drill-down."""

    scenario_id: str
    total: DeltaPosterior
    elements: list[ElementInferiority]


@dataclass(frozen=True)
class PortfolioVerdict:
    """Pooled verdict across every compared scenario — the systematic-bias signal."""

    total: DeltaPosterior
    scenario_count: int
