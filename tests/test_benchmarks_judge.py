"""Unit tests for :mod:`benchmarks.harness.judge` — quote + verdict logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import pytest

from benchmarks.harness._judge_text import (
    QUOTE_MATCH_MIN_CHARS,
    QUOTE_PARTIAL_MATCH_MIN_CHARS,
    quote_matches,
    turn_text_for_spec,
)
from benchmarks.harness._judge_vote import (
    _build_vote_from_payload,
    _coerce_verdict,
    _parse_vote_payload,
)
from benchmarks.harness.judge import JudgeCall, run_judge
from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import EvidencePromptSpec
from benchmarks.harness.types._scores import PanelMember
from cast.schemas.turn_outputs import DialogueEntry, NPCTurnEntry, TurnOutputs
from config import Config


def _turn(index: int, player_action: str, narration: str, outputs: TurnOutputs) -> CapturedTurn:
    """Build a :class:`CapturedTurn` with zero latency — deterministic for tests."""
    return CapturedTurn(
        index=index,
        player_action=player_action,
        narration=narration,
        turn_outputs=outputs,
        duration_ms=0,
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestQuoteMatching:
    @allure.story("Quote verification")
    @allure.title("quote_matches rejects empty quotes so YES with no citation never scores")
    def test_empty_quote_rejected(self):
        assert not quote_matches("", "anything at all in the turn text")

    @allure.story("Quote verification")
    @allure.title("quote_matches rejects trivially short quotes below the minimum character budget")
    def test_short_quote_rejected(self):
        short = "x" * (QUOTE_MATCH_MIN_CHARS - 1)

        assert not quote_matches(short, "{0} and more content".format(short))

    @allure.story("Quote verification")
    @allure.title("quote_matches accepts a verbatim substring of the turn text")
    def test_verbatim_substring_accepted(self):
        turn_text = "Marcus leans on his stall and mutters about the stolen wheat loaf."

        assert quote_matches("stolen wheat loaf", turn_text)

    @allure.story("Quote verification")
    @allure.title("quote_matches is case-insensitive and forgives whitespace collapsing")
    def test_normalisation_forgives_case_and_whitespace(self):
        turn_text = "Marcus\tleans on his stall."

        assert quote_matches("leans ON  his STALL", turn_text)

    @allure.story("Quote verification")
    @allure.title("quote_matches normalises newlines and leading/trailing whitespace in the quote")
    def test_normalisation_handles_newlines_and_surrounding_whitespace(self):
        turn_text = "Marcus leans on his stall."

        assert quote_matches("  leans\non\nhis stall  ", turn_text)

    @allure.story("Quote verification")
    @allure.title("quote_matches rejects a quote that does not appear in the turn text")
    def test_hallucinated_quote_rejected(self):
        turn_text = "Marcus scowls and changes the subject."

        assert not quote_matches("I suspect Gaius!", turn_text)

    @allure.story("Quote verification")
    @allure.title("quote_matches accepts ellipsis-joined fragments when each half is present in the corpus")
    def test_ellipsis_joined_fragments_accepted(self):
        turn_text = (
            "Bassus lunges in close, steps to control your arm, and drives you down hard near his boots, "
            "pinning you with his breath knocked out. "
            "His segmented plates bite into the floorboards. "
            "Cato steps in hard, catches your swing, shoves you back, and your weapon clatters away onto the boards."
        )
        quote = (
            "Bassus lunges in close, steps to control your arm, and drives you down hard near his boots, "
            "pinning you with his breath knocked out. ... "
            "Cato steps in hard, catches your swing, shoves you back, and your weapon clatters away onto the boards"
        )

        assert quote_matches(quote, turn_text)

    @allure.story("Quote verification")
    @allure.title("quote_matches accepts Unicode-ellipsis terminal truncation of an otherwise verbatim quote")
    def test_unicode_ellipsis_terminal_truncation_accepted(self):
        turn_text = (
            "Bassus says: I move in fast—short blade half-drawn, shoulder driving forward as I cut the distance. "
            "My strike lands solid; you jolt, stumble, and your footing goes—your weapon skitters "
            "away across the boards. I don't follow with a second hit; I keep you pinned with my stance."
        )
        quote = (
            "Bassus says: I move in fast—short blade half-drawn, shoulder driving forward as I cut the distance. "
            "My strike lands solid; you jolt, stumble, and your footing goes—your weapon skitters "
            "away across the boards. I don't follow with a second \u2026"
        )

        assert quote_matches(quote, turn_text)

    @allure.story("Quote verification")
    @allure.title("quote_matches rejects ellipsis-split quotes when one fragment is hallucinated")
    def test_ellipsis_fragments_rejected_when_one_hallucinated(self):
        turn_text = "Bassus lunges in close and pins you to the floorboards. Cato steps back warily."

        assert not quote_matches(
            "Bassus lunges in close and pins you to the floorboards. ... Aulus draws a crossbow and fires",
            turn_text,
        )

    @allure.story("Quote verification")
    @allure.title("quote_matches forgives a judge that wraps a verbatim spoken line in stray trailing punctuation")
    def test_partial_overlap_forgives_trailing_punctuation(self):
        turn_text = (
            "Marcus leans closer over the stall. \u201cGaius. The scarred one, by the fountain. "
            "I don't have proof, mind you\u2014just... it fits.\u201d"
        )
        quote = "\u201cGaius. The scarred one, by the fountain.\u201d"

        assert quote_matches(quote, turn_text)

    @allure.story("Quote verification")
    @allure.title("quote_matches rejects a mostly-hallucinated quote even when a short phrase overlaps the corpus")
    def test_partial_overlap_rejects_mostly_hallucinated_quote(self):
        turn_text = "The scarred guard was struck down by a thrown stool in the brawl."
        quote = "The scarred guard was struck and killed by the spear thrust from behind"

        assert not quote_matches(quote, turn_text)

    @allure.story("Quote verification")
    @allure.title("QUOTE_PARTIAL_MATCH_MIN_CHARS is tuned high enough to reject short coincidental overlaps")
    def test_partial_match_threshold_is_conservative(self):
        assert QUOTE_PARTIAL_MATCH_MIN_CHARS >= 24

    @allure.story("Quote verification")
    @allure.title("quote_matches folds Unicode smart quotes and dashes to their ASCII equivalents")
    def test_smart_punctuation_folded_to_ascii(self):
        turn_text = (
            "Brutus shifts from watching to acting just enough to startle Marcus; the concealed "
            "pugio is drawn only partway, and the room\u2019s attention turns toward the tense exchange."
        )
        quote = (
            "Brutus shifts from watching to acting just enough to startle Marcus; the concealed "
            "pugio is drawn only partway, and the room's attention turns toward the tense exchange."
        )

        assert quote_matches(quote, turn_text)

    @allure.story("Quote verification")
    @allure.title("quote_matches folds em-dashes in the corpus against a judge that used ASCII hyphens")
    def test_em_dash_folded_to_ascii(self):
        turn_text = "Gaius\u2014the scarred one by the fountain\u2014stops mid-stride and glares."
        quote = "Gaius-the scarred one by the fountain-stops mid-stride and glares"

        assert quote_matches(quote, turn_text)

    @allure.story("Quote verification")
    @allure.title("quote_matches tolerates a single punctuation drift inside an otherwise verbatim sentence")
    def test_single_comma_drift_tolerated(self):
        turn_text = (
            "He wrenches your pinned arm outward, brings his pilum up to lever your shoulder, "
            "and forces you back from the stones."
        )
        quote = (
            "He wrenches your pinned arm outward, brings his pilum up to lever your shoulder "
            "and forces you back from the stones."
        )

        assert quote_matches(quote, turn_text)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestVerdictCoercion:
    @allure.story("Verdict parsing")
    @allure.title("_coerce_verdict normalises a YES string regardless of whitespace or case")
    def test_yes_normalised(self):
        assert _coerce_verdict("YES") == "YES"
        assert _coerce_verdict(" yes ") == "YES"
        assert _coerce_verdict("Yes") == "YES"

    @allure.story("Verdict parsing")
    @allure.title("_coerce_verdict preserves NO verdicts regardless of whitespace or case")
    def test_no_preserved(self):
        assert _coerce_verdict("NO") == "NO"
        assert _coerce_verdict(" no ") == "NO"

    @allure.story("Verdict parsing")
    @allure.title("_coerce_verdict returns None for off-menu strings so they surface as ERROR abstentions")
    def test_off_menu_string_returns_none(self):
        assert _coerce_verdict("maybe") is None
        assert _coerce_verdict("") is None
        assert _coerce_verdict("yes, but") is None

    @allure.story("Verdict parsing")
    @allure.title("_coerce_verdict returns None for non-string verdicts (numbers, dicts, None)")
    def test_non_string_returns_none(self):
        assert _coerce_verdict(None) is None
        assert _coerce_verdict(42) is None
        assert _coerce_verdict({"verdict": "YES"}) is None


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestPayloadParsing:
    @allure.story("Judge payload parsing")
    @allure.title("_parse_vote_payload decodes a strict JSON object emitted on a single line")
    def test_strict_json_parse(self):
        raw = '{"verdict": "YES", "reasoning": "ok", "quote": "hello world verbatim"}'

        payload = _parse_vote_payload(raw)

        assert payload["verdict"] == "YES"
        assert payload["quote"] == "hello world verbatim"

    @allure.story("Judge payload parsing")
    @allure.title("_parse_vote_payload extracts the JSON object even when wrapped in markdown fences or chatter")
    def test_fenced_json_recovered(self):
        raw = 'Sure — here is my response:\n```json\n{"verdict": "NO", "reasoning": "nope", "quote": ""}\n```\n'

        payload = _parse_vote_payload(raw)

        assert payload["verdict"] == "NO"
        assert payload["quote"] == ""

    @allure.story("Judge payload parsing")
    @allure.title("_parse_vote_payload raises ValueError when no JSON object can be recovered from the reply")
    def test_missing_object_raises(self):
        with pytest.raises(ValueError):
            _parse_vote_payload("no json here, just prose")


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestVoteConstruction:
    @allure.story("Vote construction")
    @allure.title("_build_vote_from_payload keeps YES and marks the quote verified when the citation is genuine")
    def test_yes_with_good_quote_stays_yes(self):
        turn_text = "Marcus mutters: the stolen wheat loaf was still warm when it vanished."
        payload = {
            "verdict": "YES",
            "reasoning": "direct mention",
            "quote": "stolen wheat loaf",
        }

        vote = _build_vote_from_payload("opus", "anthropic", payload, turn_text, latency_ms=10)

        assert vote.verdict == "YES"
        assert vote.quote_verified is True
        assert vote.reasoning == "direct mention"

    @allure.story("Vote construction")
    @allure.title("_build_vote_from_payload downgrades YES to NO when the cited quote is hallucinated")
    def test_yes_with_hallucinated_quote_becomes_no(self):
        turn_text = "Marcus changes the subject."
        payload = {
            "verdict": "YES",
            "reasoning": "he mentions the loaf",
            "quote": "I suspect Gaius by the fountain",
        }

        vote = _build_vote_from_payload("opus", "anthropic", payload, turn_text, latency_ms=10)

        assert vote.verdict == "NO"
        assert vote.quote_verified is False
        assert "quote not found" in vote.reasoning

    @allure.story("Vote construction")
    @allure.title("_build_vote_from_payload downgrades YES to NO when the cited quote is too short to verify")
    def test_yes_with_short_quote_becomes_no(self):
        turn_text = "Marcus cheats."
        payload = {"verdict": "YES", "reasoning": "brief", "quote": "he"}

        vote = _build_vote_from_payload("opus", "anthropic", payload, turn_text, latency_ms=10)

        assert vote.verdict == "NO"
        assert vote.quote_verified is False

    @allure.story("Vote construction")
    @allure.title("_build_vote_from_payload preserves NO verdicts unchanged regardless of quote validity")
    def test_no_verdict_preserved(self):
        turn_text = "Marcus is silent."
        payload = {
            "verdict": "NO",
            "reasoning": "no mention",
            "quote": "",
        }

        vote = _build_vote_from_payload("haiku", "anthropic", payload, turn_text, latency_ms=5)

        assert vote.verdict == "NO"
        assert vote.quote_verified is False

    @allure.story("Vote construction")
    @allure.title("_build_vote_from_payload surfaces malformed verdicts as ERROR rather than silently scoring them NO")
    def test_malformed_verdict_becomes_error(self):
        payload = {"verdict": "MAYBE", "reasoning": "hedging", "quote": ""}

        vote = _build_vote_from_payload("opus", "anthropic", payload, "any text", latency_ms=7)

        assert vote.verdict == "ERROR"
        assert vote.error == "malformed verdict"

    @allure.story("Vote construction")
    @allure.title("_build_vote_from_payload coerces non-string reasoning/quote fields to empty strings")
    def test_non_string_reasoning_and_quote_coerced(self):
        payload: dict = {"verdict": "NO", "reasoning": None, "quote": 42}

        vote = _build_vote_from_payload("opus", "anthropic", payload, "any text", latency_ms=7)

        assert vote.reasoning == ""
        assert vote.quote == "42"


def _captured_turn_pair() -> list[CapturedTurn]:
    """Two-turn fixture — a greeting and a recall turn — used across tests."""
    greeting = TurnOutputs(
        dialogue=[DialogueEntry(npc_name="Marcus", response="Good morning!")],
    )
    recall = TurnOutputs(
        dialogue=[
            DialogueEntry(
                npc_name="Marcus",
                response="Yes — the stolen wheat loaf I spoke of yesterday.",
            ),
        ],
        npc_turns=[NPCTurnEntry(npc_name="Marcus", action="shrugs", action_type="IDLE")],
    )
    return [
        _turn(0, "greet Marcus", "The baker waves.", greeting),
        _turn(1, "ask about the loaf", "Marcus recalls the theft.", recall),
    ]


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestTurnTextExcerpt:
    @allure.story("Turn text excerpt")
    @allure.title("turn_text_for_spec narrows the excerpt to the pinned turn when evidence_turn is set")
    def test_evidence_turn_pinned(self):
        spec = EvidencePromptSpec(
            scenario_brief="brief",
            question="Does Marcus mention the loaf?",
            evidence_turn=1,
        )

        text = turn_text_for_spec(spec, _captured_turn_pair())

        assert "--- TURN 1 ---" in text
        assert "--- TURN 0 ---" not in text
        assert "stolen wheat loaf" in text

    @allure.story("Turn text excerpt")
    @allure.title("turn_text_for_spec concatenates every captured turn when evidence_turn is None")
    def test_all_turns_when_unpinned(self):
        spec = EvidencePromptSpec(
            scenario_brief="brief",
            question="Does Marcus mention the loaf?",
            evidence_turn=None,
        )

        text = turn_text_for_spec(spec, _captured_turn_pair())

        assert "--- TURN 0 ---" in text
        assert "--- TURN 1 ---" in text
        assert "Good morning!" in text
        assert "stolen wheat loaf" in text

    @allure.story("Turn text excerpt")
    @allure.title("turn_text_for_spec renders dialogue, npc_turns, and narration so judges can quote from any layer")
    def test_excerpt_covers_every_layer(self):
        spec = EvidencePromptSpec(
            scenario_brief="brief",
            question="Does Marcus say anything?",
            evidence_turn=1,
        )

        text = turn_text_for_spec(spec, _captured_turn_pair())

        assert "Marcus says" in text
        assert "[IDLE]" in text
        assert "NARRATION: Marcus recalls the theft." in text

    @allure.story("Turn text excerpt")
    @allure.title("turn_text_for_spec truncates excerpts beyond the budget with a visible marker")
    def test_excerpt_truncated_for_huge_turns(self):
        huge_narration = "x" * 8000
        huge = TurnOutputs(dialogue=[])
        turn = _turn(0, "look", huge_narration, huge)
        spec = EvidencePromptSpec(scenario_brief="b", question="q", evidence_turn=0)

        text = turn_text_for_spec(spec, [turn])

        assert len(text) < len(huge_narration) + 200
        assert "excerpt truncated" in text


def _panel_member() -> PanelMember:
    return PanelMember(provider="openai", model_id="gpt-5.4-mini")


def _judge_call(turn_text: str = "a long turn text with the stolen wheat loaf in it") -> JudgeCall:
    spec = EvidencePromptSpec(scenario_brief="b", question="q", evidence_turn=0)
    return JudgeCall(spec=spec, turn_text=turn_text)


def _cfg() -> Config:
    return Config(openai_api_key="sk-test", anthropic_api_key=None)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestRunJudge:
    @allure.story("Judge dispatch")
    @allure.title("run_judge returns a parsed JudgeVote for a well-formed LLM response")
    @pytest.mark.asyncio
    async def test_happy_path_returns_vote(self):
        body = '{"verdict": "YES", "reasoning": "cited", "quote": "stolen wheat loaf"}'
        with patch(
            "benchmarks.harness.judge._send_judge_prompt",
            new=AsyncMock(return_value=body),
        ):
            vote = await run_judge(_panel_member(), _judge_call(), cfg=_cfg())

        assert vote.verdict == "YES"
        assert vote.quote == "stolen wheat loaf"
        assert vote.error is None

    @allure.story("Judge dispatch")
    @allure.title("run_judge surfaces LLM send failures as ERROR votes tagged with a send-error reason")
    @pytest.mark.asyncio
    async def test_send_failure_becomes_error_vote(self):
        with patch(
            "benchmarks.harness.judge._send_judge_prompt",
            new=AsyncMock(side_effect=RuntimeError("connection refused")),
        ):
            vote = await run_judge(_panel_member(), _judge_call(), cfg=_cfg())

        assert vote.verdict == "ERROR"
        assert vote.error is not None
        assert "send error" in vote.error
        assert "connection refused" in vote.error

    @allure.story("Judge dispatch")
    @allure.title("run_judge surfaces unparseable bodies as ERROR votes tagged with a parse-error reason")
    @pytest.mark.asyncio
    async def test_parse_failure_becomes_error_vote(self):
        with patch(
            "benchmarks.harness.judge._send_judge_prompt",
            new=AsyncMock(return_value="nothing structured here"),
        ):
            vote = await run_judge(_panel_member(), _judge_call(), cfg=_cfg())

        assert vote.verdict == "ERROR"
        assert vote.error is not None
        assert "parse error" in vote.error
