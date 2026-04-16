"""Unit tests for :mod:`benchmarks.harness.scoring` — aggregation + clamping."""

from __future__ import annotations

import allure
import pytest

from benchmarks.harness.scoring import (
    _aggregate_verdict,
    score_deterministic_element,
)
from benchmarks.harness.types._elements import (
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.harness.types._scores import JudgeVote


def _vote(verdict: str, *, error: str | None = None) -> JudgeVote:
    """Build a minimal :class:`JudgeVote` fixture for aggregation tests."""
    return JudgeVote(
        model_id="m",
        provider="p",
        verdict=verdict,
        reasoning="",
        quote="",
        quote_verified=False,
        latency_ms=0,
        error=error,
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestAggregateVerdict:
    @allure.story("Panel aggregation")
    @allure.title("_aggregate_verdict awards a YES majority when YES votes strictly exceed NO votes")
    def test_yes_majority(self):
        votes = [_vote("YES"), _vote("YES"), _vote("YES"), _vote("YES"), _vote("NO"), _vote("NO")]

        assert _aggregate_verdict(votes) == (4, 6, "YES")

    @allure.story("Panel aggregation")
    @allure.title("_aggregate_verdict awards a NO majority when NO votes strictly exceed YES votes")
    def test_no_majority(self):
        votes = [_vote("YES"), _vote("YES"), _vote("NO"), _vote("NO"), _vote("NO"), _vote("NO")]

        assert _aggregate_verdict(votes) == (2, 6, "NO")

    @allure.story("Panel aggregation")
    @allure.title("_aggregate_verdict reports SPLIT on an even tie so judges' disagreement is visible in the report")
    def test_tie_is_split(self):
        votes = [_vote("YES"), _vote("YES"), _vote("YES"), _vote("NO"), _vote("NO"), _vote("NO")]

        assert _aggregate_verdict(votes) == (3, 6, "SPLIT")

    @allure.story("Panel aggregation")
    @allure.title("_aggregate_verdict excludes ERROR votes from n_total so flaky judges abstain rather than penalise")
    def test_error_votes_abstain(self):
        votes = [_vote("YES"), _vote("NO"), _vote("ERROR", error="timeout")]

        assert _aggregate_verdict(votes) == (1, 2, "SPLIT")

    @allure.story("Panel aggregation")
    @allure.title("_aggregate_verdict reports SPLIT with zero valid votes when every judge errored")
    def test_all_errors_produce_split_zero(self):
        votes = [_vote("ERROR"), _vote("ERROR"), _vote("ERROR")]

        assert _aggregate_verdict(votes) == (0, 0, "SPLIT")

    @allure.story("Panel aggregation")
    @allure.title("_aggregate_verdict handles an empty vote list as an all-abstain SPLIT with zero denominator")
    def test_empty_votes_produce_split_zero(self):
        assert _aggregate_verdict([]) == (0, 0, "SPLIT")


def _det_element(awarded: int, *, base: int = 3) -> Element:
    """Build a deterministic :class:`Element` whose check returns ``awarded``."""
    return Element(
        id="unit",
        label="unit",
        base_value=base,
        kind="deterministic",
        check=lambda _c, _s: DeterministicResult(awarded=awarded, reason="ok"),
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestScoreDeterministicElement:
    @allure.story("Deterministic scoring")
    @allure.title("score_deterministic_element awards the predicate's value verbatim within [0, base_value]")
    def test_awards_within_range_unmodified(self):
        score = score_deterministic_element(_det_element(2), [], [])

        assert score.awarded == 2
        assert score.base_value == 3
        assert score.reason == "ok"

    @allure.story("Deterministic scoring")
    @allure.title("score_deterministic_element clamps a negative predicate result to zero")
    def test_clamps_negative_to_zero(self):
        score = score_deterministic_element(_det_element(-5), [], [])

        assert score.awarded == 0

    @allure.story("Deterministic scoring")
    @allure.title("score_deterministic_element clamps a predicate result above base_value down to base_value")
    def test_clamps_excess_to_base_value(self):
        score = score_deterministic_element(_det_element(999, base=3), [], [])

        assert score.awarded == 3

    @allure.story("Deterministic scoring")
    @allure.title("score_deterministic_element raises TypeError when the check is not callable")
    def test_non_callable_check_raises(self):
        element = Element(
            id="bad",
            label="bad",
            base_value=1,
            kind="deterministic",
            check=EvidencePromptSpec(scenario_brief="", question=""),  # wrong shape
        )

        with pytest.raises(TypeError, match="callable check"):
            score_deterministic_element(element, [], [])

    @allure.story("Deterministic scoring")
    @allure.title("score_deterministic_element surfaces the predicate's reason and evidence_quote on the score")
    def test_score_carries_reason_and_quote(self):
        element = Element(
            id="quoted",
            label="quoted",
            base_value=1,
            kind="deterministic",
            check=lambda _c, _s: DeterministicResult(
                awarded=1,
                reason="matched",
                evidence_quote="the pie is in the oven",
            ),
        )

        score = score_deterministic_element(element, [], [])

        assert score.awarded == 1
        assert score.reason == "matched"
        assert score.evidence_quote == "the pie is in the oven"
