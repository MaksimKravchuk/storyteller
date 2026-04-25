"""SetScore builders for cross-set comparison."""

from __future__ import annotations

import allure
import pytest

from benchmarks.model_sets import _score


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark model-set comparison")
class TestSetScoreMean:
    @allure.story("Statistical properties")
    @allure.title("Empty iterations report a mean of zero rather than dividing by zero")
    def test_empty_iterations_returns_zero(self) -> None:
        score = _score.SetScore(iterations=0, total_base=10, iteration_totals=(), engine_models={})
        assert score.mean == pytest.approx(0)

    @allure.story("Statistical properties")
    @allure.title("Mean is the arithmetic average of iteration totals")
    def test_mean_averages_iteration_totals(self) -> None:
        score = _score.SetScore(iterations=3, total_base=10, iteration_totals=(6, 8, 7), engine_models={})
        assert score.mean == pytest.approx(7.0)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark model-set comparison")
class TestFromAggregate:
    @allure.story("Aggregate parsing")
    @allure.title("Reads required keys from a well-formed aggregate payload")
    def test_reads_required_keys(self) -> None:
        payload = {"iteration_totals": [6, 8, 7], "total_base": 10, "iterations": 3}
        score = _score.from_aggregate(payload, engine_models={"director_model": "gpt-5.4"})
        assert score.iterations == 3
        assert score.total_base == 10
        assert score.iteration_totals == (6, 8, 7)
        assert score.engine_models == {"director_model": "gpt-5.4"}

    @allure.story("Aggregate parsing")
    @allure.title("Iterations defaults to len(iteration_totals) when absent")
    def test_defaults_iterations_to_totals_length(self) -> None:
        payload = {"iteration_totals": [6, 8], "total_base": 10}
        score = _score.from_aggregate(payload, engine_models={})
        assert score.iterations == 2

    @allure.story("Malformed-payload safety")
    @allure.title("Missing required keys raise KeyError instead of silently scoring zero")
    @pytest.mark.parametrize("missing", ["iteration_totals", "total_base"])
    def test_raises_on_missing_required_key(self, missing: str) -> None:
        payload = {"iteration_totals": [6, 8], "total_base": 10}
        payload.pop(missing)
        with pytest.raises(KeyError):
            _score.from_aggregate(payload, engine_models={})


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark model-set comparison")
class TestFromIters:
    @allure.story("Iteration parsing")
    @allure.title("Derives iterations, total_base and engine_models from per-iter payloads")
    def test_derives_fields_from_payloads(self) -> None:
        iters = [
            {"total_awarded": 6, "total_base": 10, "engine_models": {"director_model": "gpt-5.4"}},
            {"total_awarded": 8, "total_base": 10, "engine_models": {"director_model": "gpt-5.4"}},
        ]
        score = _score.from_iters(iters)
        assert score.iterations == 2
        assert score.total_base == 10
        assert score.iteration_totals == (6, 8)
        assert score.engine_models == {"director_model": "gpt-5.4"}

    @allure.story("Malformed-payload safety")
    @allure.title("Missing total_awarded raises KeyError")
    def test_raises_on_missing_total_awarded(self) -> None:
        with pytest.raises(KeyError):
            _score.from_iters([{"total_base": 10}])

    @allure.story("Malformed-payload safety")
    @allure.title("Missing total_base raises KeyError")
    def test_raises_on_missing_total_base(self) -> None:
        with pytest.raises(KeyError):
            _score.from_iters([{"total_awarded": 6}])
