"""Element-table rendering for the markdown report."""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmarks.harness._report_text import escape_pipes, truncate_quote

if TYPE_CHECKING:
    from benchmarks.harness.types._scores import ElementScore

_CHECK = "✓"
_CROSS = "✗"
_SPLIT_SYMBOL = "⚖"
_DETERMINISTIC_QUOTE_LIMIT = 80
_EVIDENCE_QUOTE_LIMIT = 120
_DETERMINISTIC_KIND = "deterministic"


def _verdict_symbol(score: ElementScore) -> str:
    """Map an element score onto a display symbol."""
    if score.awarded == score.base_value:
        return _CHECK
    if score.awarded == 0:
        return _CROSS
    return _SPLIT_SYMBOL


def _agreement_cell(score: ElementScore) -> str:
    """Inline summary for the agreement column."""
    if score.kind == _DETERMINISTIC_KIND:
        return "det."
    if score.n_total == 0:
        return "no valid votes"
    return "{0}/{1} YES ({2})".format(score.k_yes, score.n_total, score.majority_verdict)


def _deterministic_evidence(score: ElementScore) -> str:
    """Render the evidence cell for a deterministic element."""
    reason = escape_pipes(score.reason or "")
    if score.evidence_quote:
        quote = escape_pipes(score.evidence_quote)
        return "{0} — `{1}`".format(reason, truncate_quote(quote, _DETERMINISTIC_QUOTE_LIMIT))
    return reason


def _evidence_llm_evidence(score: ElementScore) -> str:
    """Render the evidence cell for an evidence-LLM element."""
    valid_yes = [vote for vote in score.votes if vote.verdict == "YES" and vote.quote_verified]
    if valid_yes:
        quote = escape_pipes(valid_yes[0].quote)
        return "> {0}".format(truncate_quote(quote, _EVIDENCE_QUOTE_LIMIT))
    errors = [vote for vote in score.votes if vote.verdict == "ERROR"]
    if errors and score.n_total == 0:
        return "all judges errored"
    return "no quote cited by any witness"


def _evidence_cell(score: ElementScore) -> str:
    """Render the most informative cited quote or reason on one line."""
    if score.kind == _DETERMINISTIC_KIND:
        return _deterministic_evidence(score)
    return _evidence_llm_evidence(score)


def _table_row(score: ElementScore) -> str:
    """Format one element score as a GFM table row."""
    return "| {label} | {verdict} | {awarded}/{base} | {agreement} | {evidence} |".format(
        label=escape_pipes(score.label),
        verdict=_verdict_symbol(score),
        awarded=score.awarded,
        base=score.base_value,
        agreement=_agreement_cell(score),
        evidence=_evidence_cell(score),
    )


def render_element_table(scores: list[ElementScore]) -> list[str]:
    """Render the one-row-per-element score table."""
    lines = [
        "## Elements",
        "",
        "| Element | Verdict | Points | Agreement | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(_table_row(score) for score in scores)
    return lines
