"""Parse raw judge replies into :class:`JudgeVote` records.

These helpers cover everything *after* the judge LLM has returned its
body: JSON extraction, verdict normalisation, quote verification, and
building the final :class:`JudgeVote`. The network-facing dispatch
lives in :mod:`benchmarks.harness.judge`.
"""

from __future__ import annotations

import json

from benchmarks.harness._judge_text import _quote_matches
from benchmarks.harness.types._scores import JudgeVote, PanelMember

_VERDICT_YES = "YES"
_VERDICT_NO = "NO"
_VERDICT_ERROR = "ERROR"


def _parse_vote_payload(raw: str) -> dict:
    """Extract the judge's JSON object from its raw text reply.

    Judges occasionally wrap their JSON in markdown fences or chatty
    prose even when instructed not to. We try strict parse first, then
    fall back to an outermost-braces extraction; anything else raises
    ``ValueError``.
    """
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            raise ValueError("Judge produced no JSON object")
        return json.loads(text[start:end])


def _coerce_verdict(verdict_field: object) -> str:
    """Normalise a judge's verdict string to the ``YES``/``NO`` alphabet.

    Any off-menu response collapses to ``NO`` — a judge that cannot
    commit to a clear verdict does not get to award credit.
    """
    if not isinstance(verdict_field, str):
        return _VERDICT_NO
    if verdict_field.strip().upper() == _VERDICT_YES:
        return _VERDICT_YES
    return _VERDICT_NO


def _build_vote_from_payload(
    model_id: str,
    provider: str,
    payload: dict,
    turn_text: str,
    latency_ms: int,
) -> JudgeVote:
    """Turn a parsed judge payload into a :class:`JudgeVote`.

    A verdict of YES with a hallucinated or missing quote is downgraded
    to NO — the quote is the evidence, so no quote means no credit.
    """
    verdict = _coerce_verdict(payload.get("verdict"))
    reasoning = str(payload.get("reasoning") or "").strip()
    quote = str(payload.get("quote") or "").strip()
    quote_ok = _quote_matches(quote, turn_text)
    if verdict == _VERDICT_YES and not quote_ok:
        verdict = _VERDICT_NO
        reasoning = "{0} (quote not found in turn text)".format(reasoning).strip()
    return JudgeVote(
        model_id=model_id,
        provider=provider,
        verdict=verdict,
        reasoning=reasoning,
        quote=quote,
        quote_verified=quote_ok,
        latency_ms=latency_ms,
    )


def _error_vote(member: PanelMember, latency_ms: int, error: str) -> JudgeVote:
    """Build an ``ERROR`` vote with empty quote + reasoning."""
    return JudgeVote(
        model_id=member.model_id,
        provider=member.provider,
        verdict=_VERDICT_ERROR,
        reasoning="",
        quote="",
        quote_verified=False,
        latency_ms=latency_ms,
        error=error,
    )
