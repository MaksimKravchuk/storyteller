"""Unit tests for :mod:`benchmarks.harness.scoring` — aggregation + clamping."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import pytest

from benchmarks.harness.scoring import (
    _aggregate_verdict,
    _evidence_awarded,
    score_deterministic_element,
    score_evidence_element,
    score_scenario,
)
from benchmarks.harness.types._elements import (
    KIND_DETERMINISTIC,
    KIND_EVIDENCE_LLM,
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.harness.types._scores import JudgeVote, PanelMember
from config import Config


def _vote(verdict: str, *, error: str | None = None) -> JudgeVote:
    """Build a minimal :class:`JudgeVote` fixture for aggregation tests."""
    return JudgeVote(
        model_id="m",
        provider="p",
        verdict=verdict,  # type: ignore[arg-type]
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
    @allure.title("_aggregate_verdict reports PANEL_COLLAPSED with zero valid votes when every judge errored")
    def test_all_errors_produce_panel_collapsed(self):
        votes = [_vote("ERROR"), _vote("ERROR"), _vote("ERROR")]

        assert _aggregate_verdict(votes) == (0, 0, "PANEL_COLLAPSED")

    @allure.story("Panel aggregation")
    @allure.title("_aggregate_verdict reports PANEL_COLLAPSED on an empty vote list (no judges dispatched)")
    def test_empty_votes_produce_panel_collapsed(self):
        assert _aggregate_verdict([]) == (0, 0, "PANEL_COLLAPSED")


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestEvidenceAwarded:
    @allure.story("Evidence scoring")
    @allure.title("_evidence_awarded returns zero when no judges voted, avoiding divide-by-zero")
    def test_zero_total_returns_zero(self):
        assert _evidence_awarded(base_value=3, k_yes=0, n_total=0) == 0

    @allure.story("Evidence scoring")
    @allure.title("_evidence_awarded returns the full base_value when every valid judge voted YES")
    def test_full_yes_awards_base_value(self):
        assert _evidence_awarded(base_value=3, k_yes=4, n_total=4) == 3

    @allure.story("Evidence scoring")
    @allure.title("_evidence_awarded scales points proportionally and rounds to the nearest integer")
    def test_partial_credit_rounded(self):
        # 3 * 2 / 3 = 2.0 → 2
        assert _evidence_awarded(base_value=3, k_yes=2, n_total=3) == 2
        # 3 * 1 / 3 = 1.0 → 1
        assert _evidence_awarded(base_value=3, k_yes=1, n_total=3) == 1
        # 5 * 1 / 3 = 1.667 → 2
        assert _evidence_awarded(base_value=5, k_yes=1, n_total=3) == 2


def _det_element(awarded: int, *, base: int = 3) -> Element:
    """Build a deterministic :class:`Element` whose check returns ``awarded``."""
    return Element(
        id="unit",
        label="unit",
        base_value=base,
        kind=KIND_DETERMINISTIC,
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
    @allure.title("score_deterministic_element clamps a predicate result above base_value down to base_value")
    def test_clamps_excess_to_base_value(self):
        score = score_deterministic_element(_det_element(999, base=3), [], [])

        assert score.awarded == 3

    @allure.story("Deterministic scoring")
    @allure.title("score_deterministic_element surfaces the predicate's reason and evidence_quote on the score")
    def test_score_carries_reason_and_quote(self):
        element = Element(
            id="quoted",
            label="quoted",
            base_value=1,
            kind=KIND_DETERMINISTIC,
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


def _cfg() -> Config:
    return Config(openai_api_key="sk-test", anthropic_api_key=None)


def _panel() -> list[PanelMember]:
    return [PanelMember(provider="openai", model_id="gpt-x")]


def _evidence_element() -> Element:
    return Element(
        id="stolen_loaf",
        label="mentions loaf",
        base_value=3,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(scenario_brief="b", question="q", evidence_turn=None),
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestScoreEvidenceElement:
    @allure.story("Evidence scoring")
    @allure.title("score_evidence_element awards proportional credit from the witness panel's valid YES votes")
    @pytest.mark.asyncio
    async def test_awards_proportional_credit(self):
        fake_votes = [_vote("YES"), _vote("YES"), _vote("NO")]
        with patch("benchmarks.harness.scoring.run_judge", new=AsyncMock(side_effect=fake_votes)):
            score = await score_evidence_element(
                _evidence_element(),
                captured_turns=[],
                panel=[PanelMember(provider="p", model_id="m{0}".format(idx)) for idx in range(3)],
                cfg=_cfg(),
            )

        assert score.k_yes == 2
        assert score.n_total == 3
        assert score.majority_verdict == "YES"
        assert score.awarded == 2  # round(3 * 2 / 3) = 2
        assert len(score.votes) == 3

    @allure.story("Evidence scoring")
    @allure.title("score_evidence_element records PANEL_COLLAPSED and awards zero when every judge errored")
    @pytest.mark.asyncio
    async def test_panel_collapsed_awards_zero(self):
        fake_votes = [_vote("ERROR", error="timeout"), _vote("ERROR", error="timeout")]
        with patch("benchmarks.harness.scoring.run_judge", new=AsyncMock(side_effect=fake_votes)):
            score = await score_evidence_element(
                _evidence_element(),
                captured_turns=[],
                panel=[PanelMember(provider="p", model_id="a"), PanelMember(provider="p", model_id="b")],
                cfg=_cfg(),
            )

        assert score.majority_verdict == "PANEL_COLLAPSED"
        assert score.awarded == 0
        assert score.n_total == 0

    @allure.story("Evidence scoring")
    @allure.title("score_evidence_element raises TypeError when the element's check is not an EvidencePromptSpec")
    @pytest.mark.asyncio
    async def test_non_spec_check_raises(self):
        # Build a wrong-shape element by bypassing __post_init__ (evidence element
        # with a callable check would fail validation).
        bad_element = Element(
            id="bad",
            label="bad",
            base_value=1,
            kind=KIND_DETERMINISTIC,
            check=lambda _c, _s: DeterministicResult(awarded=0, reason=""),
        )

        with pytest.raises(TypeError, match="EvidencePromptSpec"):
            await score_evidence_element(bad_element, captured_turns=[], panel=_panel(), cfg=_cfg())


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestScoreScenario:
    @allure.story("Scenario scoring")
    @allure.title("score_scenario preserves element order and dispatches each kind to its scorer")
    @pytest.mark.asyncio
    async def test_order_preserved_mixed_kinds(self):
        det = _det_element(2, base=3)
        evidence = _evidence_element()
        fake_votes = [_vote("YES")]
        with patch("benchmarks.harness.scoring.run_judge", new=AsyncMock(side_effect=fake_votes)):
            scores = await score_scenario(
                elements=[det, evidence],
                captured_turns=[],
                snapshots=[],
                panel=[PanelMember(provider="p", model_id="x")],
                cfg=_cfg(),
            )

        assert [score.element_id for score in scores] == [det.id, evidence.id]
        assert scores[0].awarded == 2  # deterministic
        assert scores[1].awarded == 3  # evidence full credit (1/1 YES)

    @allure.story("Scenario scoring")
    @allure.title("score_scenario returns an empty list when no elements are supplied")
    @pytest.mark.asyncio
    async def test_empty_elements_yields_empty_scores(self):
        scores = await score_scenario(
            elements=[],
            captured_turns=[],
            snapshots=[],
            panel=[],
            cfg=_cfg(),
        )

        assert scores == []
