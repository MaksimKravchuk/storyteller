"""Turn-text rendering and quote verification for the evidence-LLM judges."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import EvidencePromptSpec

QUOTE_MATCH_MIN_CHARS = 8
QUOTE_PARTIAL_MATCH_MIN_CHARS = 24
QUOTE_PARTIAL_MATCH_MIN_RATIO = 0.9
_TURN_EXCERPT_CHAR_BUDGET = 4000
_TRUNCATION_NOTE = "\n[...excerpt truncated...]"
_ELLIPSIS_PATTERN = re.compile(r"\.{3,}|\u2026")
_SMART_PUNCTUATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
    },
)


def _normalise(text: str) -> str:
    """Lowercase, fold smart punctuation, and collapse whitespace for forgiving matching."""
    folded = text.translate(_SMART_PUNCTUATION)
    return re.sub(r"\s+", " ", folded.strip().lower())


def _ellipsis_fragments_present(normalised_quote: str, normalised_corpus: str) -> bool:
    """Return True when the quote is a concat of corpus spans joined by ellipsis markers."""
    raw_fragments = _ELLIPSIS_PATTERN.split(normalised_quote)
    fragments = [fragment.strip() for fragment in raw_fragments if fragment.strip()]
    if len(fragments) < 2:
        return False
    return all(fragment in normalised_corpus for fragment in fragments)


def _matching_char_count(normalised_quote: str, normalised_corpus: str) -> int:
    """Return the total characters of the quote that align, in order, with the corpus."""
    matcher = SequenceMatcher(None, normalised_quote, normalised_corpus, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks())


def _partial_overlap_accepted(normalised_quote: str, normalised_corpus: str) -> bool:
    """Return True when the quote is overwhelmingly grounded in corpus text, up to small drift."""
    if not normalised_quote or not normalised_corpus:
        return False
    matched = _matching_char_count(normalised_quote, normalised_corpus)
    if matched < QUOTE_PARTIAL_MATCH_MIN_CHARS:
        return False
    return matched / len(normalised_quote) >= QUOTE_PARTIAL_MATCH_MIN_RATIO


def quote_matches(quote: str, turn_text: str) -> bool:
    """Return True when ``quote`` is grounded in ``turn_text`` up to harmless drift."""
    if not quote or len(quote.strip()) < QUOTE_MATCH_MIN_CHARS:
        return False
    normalised_quote = _normalise(quote)
    normalised_corpus = _normalise(turn_text)
    if normalised_quote in normalised_corpus:
        return True
    if _ellipsis_fragments_present(normalised_quote, normalised_corpus):
        return True
    return _partial_overlap_accepted(normalised_quote, normalised_corpus)


def _render_turn(turn: CapturedTurn) -> list[str]:
    """Format one captured turn as a list of lines for judge consumption."""
    lines = [
        "--- TURN {0} ---".format(turn.index),
        "PLAYER: {0}".format(turn.player_action),
    ]
    for entry in turn.turn_outputs.dialogue:
        contest = " [{0}]".format(entry.contest_roll) if entry.contest_roll else ""
        lines.append("{0} says{1}: {2}".format(entry.npc_name, contest, entry.response))
    for npc_turn in turn.turn_outputs.npc_turns:
        lines.append(
            "{0} [{1}]: {2}".format(npc_turn.npc_name, npc_turn.action_type, npc_turn.action),
        )
    for interaction in turn.turn_outputs.object_interactions:
        lines.append("OBJECT: {0}".format(interaction))
    lines.append("NARRATION: {0}".format(turn.narration))
    return lines


def turn_text_for_spec(spec: EvidencePromptSpec, captured_turns: list[CapturedTurn]) -> str:
    """Return the captured text the spec pins to, concatenated when unpinned."""
    if spec.evidence_turn is None:
        turns: list[CapturedTurn] = list(captured_turns)
    else:
        turns = [captured_turns[spec.evidence_turn]]
    parts: list[str] = []
    for turn in turns:
        parts.extend(_render_turn(turn))
    joined = "\n".join(parts)
    if len(joined) > _TURN_EXCERPT_CHAR_BUDGET:
        return "{0}{1}".format(joined[:_TURN_EXCERPT_CHAR_BUDGET], _TRUNCATION_NOTE)
    return joined
