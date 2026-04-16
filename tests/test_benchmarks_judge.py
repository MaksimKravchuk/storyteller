"""Unit tests for :mod:`benchmarks.harness.judge` — quote + verdict logic.

The network-facing :func:`run_judge` wrapper is not exercised here; only
the pure helpers that parse payloads, normalise quotes, and coerce
verdicts — that is where the interesting behaviour lives.
"""

from __future__ import annotations

import allure
import pytest

from benchmarks.harness._judge_text import (
    _QUOTE_MATCH_MIN_CHARS,
    _quote_matches,
    turn_text_for_spec,
)
from benchmarks.harness._judge_vote import (
    _build_vote_from_payload,
    _coerce_verdict,
    _parse_vote_payload,
)
from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import EvidencePromptSpec
from cast.schemas.turn_outputs import DialogueEntry, NPCTurnEntry, TurnOutputs


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
    @allure.title("_quote_matches rejects empty quotes so YES with no citation never scores")
    def test_empty_quote_rejected(self):
        assert not _quote_matches("", "anything at all in the turn text")

    @allure.story("Quote verification")
    @allure.title("_quote_matches rejects trivially short quotes below the minimum character budget")
    def test_short_quote_rejected(self):
        short = "x" * (_QUOTE_MATCH_MIN_CHARS - 1)

        assert not _quote_matches(short, "{0} and more content".format(short))

    @allure.story("Quote verification")
    @allure.title("_quote_matches accepts a verbatim substring of the turn text")
    def test_verbatim_substring_accepted(self):
        turn_text = "Marcus leans on his stall and mutters about the stolen wheat loaf."

        assert _quote_matches("stolen wheat loaf", turn_text)

    @allure.story("Quote verification")
    @allure.title("_quote_matches is case-insensitive and forgives whitespace collapsing")
    def test_normalisation_forgives_case_and_whitespace(self):
        turn_text = "Marcus\tleans on his stall."

        assert _quote_matches("leans ON  his STALL", turn_text)

    @allure.story("Quote verification")
    @allure.title("_quote_matches rejects a quote that does not appear in the turn text")
    def test_hallucinated_quote_rejected(self):
        turn_text = "Marcus scowls and changes the subject."

        assert not _quote_matches("I suspect Gaius!", turn_text)


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
    @allure.title("_coerce_verdict collapses every non-YES string to NO so fence-sitters do not score")
    def test_non_yes_becomes_no(self):
        assert _coerce_verdict("NO") == "NO"
        assert _coerce_verdict("maybe") == "NO"
        assert _coerce_verdict("") == "NO"

    @allure.story("Verdict parsing")
    @allure.title("_coerce_verdict returns NO when passed a non-string verdict (None, numbers, dicts)")
    def test_non_string_returns_no(self):
        assert _coerce_verdict(None) == "NO"
        assert _coerce_verdict(42) == "NO"
        assert _coerce_verdict({"verdict": "YES"}) == "NO"


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
