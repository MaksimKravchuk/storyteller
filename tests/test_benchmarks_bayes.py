"""Unit tests for the Bayesian benchmark-comparison layer."""

from __future__ import annotations

import allure
import pytest

from benchmarks.harness.bayes._beta import element_inferiority
from benchmarks.harness.bayes._beta_quadrature import prob_below
from benchmarks.harness.bayes._normal import (
    normal_cdf,
    pool_deltas,
    scenario_delta_posterior,
)
from benchmarks.harness.bayes._report import portfolio_verdict, verdict_for_scenario
from benchmarks.harness.bayes._types import BetaParams, Sample, VoteCounts


def _rate(element_id: str, *, passes: int, iterations: int, k_yes: int = 0, n_votes: int = 0) -> dict:
    return {
        "element_id": element_id,
        "label": element_id,
        "base_value": 2,
        "passes": passes,
        "iterations": iterations,
        "k_yes": k_yes,
        "n_votes": n_votes,
    }


def _aggregate(*, scenario_id: str, mean: float, iterations: int, rates: list[dict] | None = None) -> dict:
    return {
        "scenario_id": scenario_id,
        "mean_awarded": mean,
        "iterations": iterations,
        "element_pass_rates": rates or [],
    }


_NEAR_CERTAIN = 0.99
_NEGLIGIBLE = 0.01
_CONFIDENT = 0.94
_HIGH = 0.9
_AMBIGUOUS = 0.75
_HALF = 0.5


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestNormalCdf:
    @allure.story("Bayesian compare")
    @allure.title("normal_cdf matches standard-normal reference points")
    def test_reference_points(self):
        assert normal_cdf(0, 0, 1) == pytest.approx(0.5)
        assert normal_cdf(1.959963984540054, 0, 1) == pytest.approx(0.975, abs=1e-4)
        assert normal_cdf(-1.959963984540054, 0, 1) == pytest.approx(0.025, abs=1e-4)

    @allure.story("Bayesian compare")
    @allure.title("normal_cdf collapses to a step function when stdev is zero")
    def test_degenerate_stdev(self):
        assert normal_cdf(4.9, 5.0, 0) == float(0)
        assert normal_cdf(5.0, 5.0, 0) == float(1)
        assert normal_cdf(5.1, 5.0, 0) == float(1)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestScenarioDelta:
    @allure.story("Bayesian compare")
    @allure.title("scenario delta posterior centres on current minus baseline mean")
    def test_delta_mean(self):
        posterior = scenario_delta_posterior(
            Sample(mean=14.67, iterations=3),
            Sample(mean=14.0, iterations=1),
            noise_floor_stdev=0.94,
            rope=0.5,
        )
        assert posterior.delta_mean == pytest.approx(-0.67)
        assert posterior.delta_stdev > 0

    @allure.story("Bayesian compare")
    @allure.title("the three posterior masses sum to one")
    def test_masses_partition(self):
        posterior = scenario_delta_posterior(
            Sample(mean=10.0, iterations=3),
            Sample(mean=8.0, iterations=1),
            noise_floor_stdev=1.2,
            rope=0.5,
        )
        total = posterior.p_regression + posterior.p_improvement + posterior.p_equivalent
        assert total == pytest.approx(1.0)

    @allure.story("Bayesian compare")
    @allure.title("a large downward shift with small noise yields high regression probability")
    def test_clear_regression(self):
        posterior = scenario_delta_posterior(
            Sample(mean=10.0, iterations=3),
            Sample(mean=6.0, iterations=3),
            noise_floor_stdev=0.5,
            rope=0.5,
        )
        assert posterior.p_regression > _NEAR_CERTAIN

    @allure.story("Bayesian compare")
    @allure.title("a zero noise floor produces a degenerate point-mass verdict")
    def test_zero_noise_floor_is_degenerate(self):
        posterior = scenario_delta_posterior(
            Sample(mean=10.0, iterations=3),
            Sample(mean=8.0, iterations=1),
            noise_floor_stdev=0,
            rope=0.5,
        )
        assert posterior.delta_stdev == 0
        assert posterior.p_regression == float(1)
        assert posterior.ci_low == posterior.ci_high == posterior.delta_mean

    @allure.story("Bayesian compare")
    @allure.title("equal means leave the posterior dominated by practical equivalence")
    def test_equivalent_when_no_shift(self):
        posterior = scenario_delta_posterior(
            Sample(mean=7.0, iterations=3),
            Sample(mean=7.0, iterations=3),
            noise_floor_stdev=0.4,
            rope=0.5,
        )
        assert posterior.p_equivalent > posterior.p_regression
        assert posterior.p_equivalent > posterior.p_improvement
        assert posterior.p_regression == pytest.approx(posterior.p_improvement, abs=1e-9)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestPoolDeltas:
    @allure.story("Bayesian compare")
    @allure.title("pooling sums delta means and adds variances")
    def test_sum_and_variance(self):
        one = scenario_delta_posterior(
            Sample(mean=10.0, iterations=3),
            Sample(mean=9.5, iterations=3),
            noise_floor_stdev=1.0,
            rope=float(0),
        )
        pooled = pool_deltas([one, one], rope=float(0))
        assert pooled.delta_mean == pytest.approx(2 * one.delta_mean)
        assert pooled.delta_stdev == pytest.approx(one.delta_stdev * 2**0.5)

    @allure.story("Bayesian compare")
    @allure.title("pooling many small consistent dips detects a systematic bias each scenario hides")
    def test_portfolio_detects_systematic_drift(self):
        # Each scenario alone is ambiguous: a -0.6 dip against a 1.0 noise floor.
        dips = [
            scenario_delta_posterior(
                Sample(mean=10.0, iterations=3),
                Sample(mean=9.4, iterations=1),
                noise_floor_stdev=1.0,
                rope=float(0),
            )
            for _ in range(10)
        ]
        assert all(dip.p_regression < _AMBIGUOUS for dip in dips)

        pooled = pool_deltas(dips, rope=float(0))

        # Pooling concentrates the evidence: ~0.95 confident where each was ~0.70.
        assert pooled.p_regression > _CONFIDENT
        assert pooled.p_regression > max(dip.p_regression for dip in dips)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestProbBelow:
    @allure.story("Bayesian compare")
    @allure.title("identical Beta posteriors give a coin-flip inferiority probability")
    def test_identical(self):
        prob = prob_below(BetaParams(3, 3), BetaParams(3, 3))
        assert prob == pytest.approx(0.5, abs=2e-3)

    @allure.story("Bayesian compare")
    @allure.title("prob_below matches the analytic E[Y] for current uniform vs baseline Beta(2,1)")
    def test_analytic_uniform_vs_beta(self):
        # current ~ U(0,1), baseline ~ Beta(2,1): P(X<Y) = E[Y] = 2/3.
        prob = prob_below(BetaParams(2, 1), BetaParams(1, 1))
        assert prob == pytest.approx(2 / 3, abs=2e-3)

    @allure.story("Bayesian compare")
    @allure.title("prob_below matches the analytic E[X**2] for current Beta(2,1) vs baseline uniform")
    def test_analytic_beta_vs_uniform(self):
        # current ~ Beta(2,1), baseline ~ U(0,1): P(Y<X) = E[X**2] = 1/3.
        prob = prob_below(BetaParams(1, 1), BetaParams(2, 1))
        assert prob == pytest.approx(1 / 3, abs=2e-3)

    @allure.story("Bayesian compare")
    @allure.title("a current posterior shifted low scores high inferiority probability")
    def test_current_below(self):
        assert prob_below(BetaParams(7, 1), BetaParams(1, 7)) > _NEAR_CERTAIN

    @allure.story("Bayesian compare")
    @allure.title("a current posterior shifted high scores low inferiority probability")
    def test_current_above(self):
        assert prob_below(BetaParams(1, 7), BetaParams(7, 1)) < _NEGLIGIBLE


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestElementInferiority:
    @allure.story("Bayesian compare")
    @allure.title("judge votes are preferred over iteration pass-counts when present")
    def test_prefers_judge_votes(self):
        verdict = element_inferiority(
            "e1",
            "e1",
            VoteCounts(yes=16, votes=18, passes=3, iterations=3),
            VoteCounts(yes=2, votes=6, passes=1, iterations=1),
        )
        assert verdict.resolution == "judges"
        assert verdict.p_regression > _HIGH
        assert verdict.p_improvement == pytest.approx(1 - verdict.p_regression)

    @allure.story("Bayesian compare")
    @allure.title("falls back to iteration pass-counts when no judge votes are retained")
    def test_iteration_fallback(self):
        verdict = element_inferiority(
            "e1",
            "e1",
            VoteCounts(yes=0, votes=0, passes=3, iterations=3),
            VoteCounts(yes=0, votes=0, passes=0, iterations=1),
        )
        assert verdict.resolution == "iterations"
        assert verdict.p_regression > _HALF

    @allure.story("Bayesian compare")
    @allure.title("reports 'none' resolution and a coin-flip when no data exists either way")
    def test_no_data(self):
        verdict = element_inferiority(
            "e1",
            "e1",
            VoteCounts(yes=0, votes=0, passes=0, iterations=0),
            VoteCounts(yes=0, votes=0, passes=0, iterations=0),
        )
        assert verdict.resolution == "none"
        assert verdict.p_regression == pytest.approx(0.5, abs=2e-3)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestVerdictForScenario:
    @allure.story("Bayesian compare")
    @allure.title("scenario verdict matches elements by id and skips unmatched ones")
    def test_matches_elements_by_id(self):
        baseline = _aggregate(
            scenario_id="s1",
            mean=10.0,
            iterations=3,
            rates=[_rate("kept", passes=3, iterations=3), _rate("dropped", passes=3, iterations=3)],
        )
        current = _aggregate(
            scenario_id="s1",
            mean=8.0,
            iterations=1,
            rates=[_rate("kept", passes=0, iterations=1), _rate("added", passes=1, iterations=1)],
        )

        verdict = verdict_for_scenario(baseline, current, noise_floor_stdev=1.0)

        assert verdict.scenario_id == "s1"
        assert [element.element_id for element in verdict.elements] == ["kept"]
        assert verdict.total.delta_mean == pytest.approx(-2.0)

    @allure.story("Bayesian compare")
    @allure.title("portfolio verdict pools scenario totals and counts them")
    def test_portfolio_pools(self):
        baseline = _aggregate(scenario_id="s", mean=10.0, iterations=3)
        verdicts = [
            verdict_for_scenario(
                baseline,
                _aggregate(scenario_id="s{0}".format(idx), mean=9.4, iterations=1),
                noise_floor_stdev=1.0,
                rope=float(0),
            )
            for idx in range(10)
        ]

        portfolio = portfolio_verdict(verdicts, rope=float(0))

        assert portfolio.scenario_count == 10
        assert portfolio.total.p_regression > _CONFIDENT
