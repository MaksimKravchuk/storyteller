"""Assemble Bayesian verdicts from aggregate dicts (baseline vs current)."""

from __future__ import annotations

from benchmarks.harness.bayes._beta import element_inferiority
from benchmarks.harness.bayes._normal import pool_deltas, scenario_delta_posterior
from benchmarks.harness.bayes._types import (
    ElementInferiority,
    PortfolioVerdict,
    Sample,
    ScenarioVerdict,
    VoteCounts,
)

DEFAULT_ROPE = 0.5  # score-points of practical equivalence on a scenario total
_KEY_ITERATIONS = "iterations"


def _counts(rate: dict) -> VoteCounts:
    """Build per-element tallies from a pass-rate dict (judge votes + pass-counts)."""
    return VoteCounts(
        yes=rate.get("k_yes", 0),
        votes=rate.get("n_votes", 0),
        passes=rate["passes"],
        iterations=rate[_KEY_ITERATIONS],
    )


def _sample(aggregate: dict) -> Sample:
    """Build a total-score sample from an aggregate dict."""
    return Sample(mean=aggregate["mean_awarded"], iterations=aggregate[_KEY_ITERATIONS])


def _element_verdict(baseline_rate: dict, current_rate: dict) -> ElementInferiority:
    """Build one element verdict from baseline + current pass-rate dicts."""
    return element_inferiority(
        current_rate["element_id"],
        current_rate["label"],
        _counts(baseline_rate),
        _counts(current_rate),
    )


def _element_verdicts(baseline: dict, current: dict) -> list[ElementInferiority]:
    """Match elements by id and build a verdict for each shared element."""
    baseline_index = {rate["element_id"]: rate for rate in baseline.get("element_pass_rates", [])}
    verdicts: list[ElementInferiority] = []
    for current_rate in current.get("element_pass_rates", []):
        baseline_rate = baseline_index.get(current_rate["element_id"])
        if baseline_rate is not None:
            verdicts.append(_element_verdict(baseline_rate, current_rate))
    return verdicts


def verdict_for_scenario(
    baseline: dict,
    current: dict,
    *,
    noise_floor_stdev: float,
    rope: float = DEFAULT_ROPE,
) -> ScenarioVerdict:
    """Bayesian verdict for one scenario: total-score delta plus element drill-down."""
    total = scenario_delta_posterior(
        _sample(baseline),
        _sample(current),
        noise_floor_stdev=noise_floor_stdev,
        rope=rope,
    )
    return ScenarioVerdict(
        scenario_id=current["scenario_id"],
        total=total,
        elements=_element_verdicts(baseline, current),
    )


def portfolio_verdict(scenarios: list[ScenarioVerdict], *, rope: float = DEFAULT_ROPE) -> PortfolioVerdict:
    """Pool every scenario's total delta into one systematic-bias posterior."""
    pooled = pool_deltas([scenario.total for scenario in scenarios], rope=rope)
    return PortfolioVerdict(total=pooled, scenario_count=len(scenarios))
