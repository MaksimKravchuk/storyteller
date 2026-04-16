"""Turn-text rendering and quote verification for the evidence-LLM judges."""

from __future__ import annotations

import re

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import EvidencePromptSpec

QUOTE_MATCH_MIN_CHARS = 8
_TURN_EXCERPT_CHAR_BUDGET = 4000
_TRUNCATION_NOTE = "\n[...excerpt truncated...]"


def _normalise(text: str) -> str:
    """Lowercase and collapse whitespace so quote matching is forgiving."""
    return re.sub(r"\s+", " ", text.strip().lower())


def quote_matches(quote: str, turn_text: str) -> bool:
    """Return True when ``quote`` is a normalised substring of ``turn_text``."""
    if not quote or len(quote.strip()) < QUOTE_MATCH_MIN_CHARS:
        return False
    return _normalise(quote) in _normalise(turn_text)


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
