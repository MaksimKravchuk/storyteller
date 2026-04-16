"""Parse raw judge replies into ``JudgeVote`` records."""

from __future__ import annotations

import json

from benchmarks.harness._judge_text import quote_matches
from benchmarks.harness.types._scores import JudgeVerdict, JudgeVote, PanelMember

_VERDICT_YES: JudgeVerdict = "YES"
_VERDICT_NO: JudgeVerdict = "NO"
_VERDICT_ERROR: JudgeVerdict = "ERROR"
_PARSEABLE_VERDICTS = frozenset((_VERDICT_YES, _VERDICT_NO))
_MALFORMED_VERDICT_ERROR = "malformed verdict"
_MALFORMED_QUOTE_REASONING = "(quote not found in turn text)"


def _parse_vote_payload(raw: str) -> dict:
    """Extract the judge's JSON object from its raw reply."""
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            raise ValueError("Judge produced no JSON object") from exc
        return json.loads(text[start:end])


def _coerce_verdict(verdict_field: object) -> JudgeVerdict | None:
    """Normalise a judge's verdict to YES or NO. Returns None on malformed input."""
    if not isinstance(verdict_field, str):
        return None
    upper = verdict_field.strip().upper()
    if upper in _PARSEABLE_VERDICTS:
        return upper  # type: ignore[return-value]
    return None


def _build_vote_from_payload(
    model_id: str,
    provider: str,
    payload: dict,
    turn_text: str,
    latency_ms: int,
) -> JudgeVote:
    """Turn a parsed judge payload into a :class:`JudgeVote`."""
    verdict = _coerce_verdict(payload.get("verdict"))
    reasoning = str(payload.get("reasoning") or "").strip()
    quote = str(payload.get("quote") or "").strip()
    if verdict is None:
        return JudgeVote(
            model_id=model_id,
            provider=provider,
            verdict=_VERDICT_ERROR,
            reasoning=reasoning,
            quote=quote,
            quote_verified=False,
            latency_ms=latency_ms,
            error=_MALFORMED_VERDICT_ERROR,
        )
    quote_ok = quote_matches(quote, turn_text)
    if verdict == _VERDICT_YES and not quote_ok:
        verdict = _VERDICT_NO
        reasoning = "{0} {1}".format(reasoning, _MALFORMED_QUOTE_REASONING).strip()
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
