"""Witness vote appendix — per-element judge-by-judge disclosure."""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmarks.harness._report_text import truncate_quote

if TYPE_CHECKING:
    from benchmarks.harness.types._scores import ElementScore, JudgeVote

_APPENDIX_QUOTE_LIMIT = 240
_EVIDENCE_KIND = "evidence_llm"
_NO_REASONING_PLACEHOLDER = "(no reasoning)"


def _vote_status_tag(vote: JudgeVote) -> str:
    """Short ``YES/NO/ERROR`` tag for appendix rows, including quote state."""
    if vote.verdict == "ERROR":
        return "ERROR ({0})".format(vote.error or "unknown")
    suffix = "" if vote.quote_verified else " (no valid quote)"
    return "{0}{1}".format(vote.verdict, suffix)


def _vote_line(vote: JudgeVote) -> str:
    """Format one judge's vote as an appendix bullet."""
    return "- **{model}** ({provider}) — {status} — {reasoning}".format(
        model=vote.model_id,
        provider=vote.provider,
        status=_vote_status_tag(vote),
        reasoning=vote.reasoning or _NO_REASONING_PLACEHOLDER,
    )


def _vote_entries(votes: list[JudgeVote]) -> list[str]:
    """Render every vote for one element (bullet + optional quote)."""
    lines: list[str] = []
    for vote in votes:
        lines.append(_vote_line(vote))
        if vote.quote:
            lines.append("    > {0}".format(truncate_quote(vote.quote, _APPENDIX_QUOTE_LIMIT)))
    return lines


def _element_section(score: ElementScore) -> list[str]:
    """Render the appendix block for one evidence-LLM element."""
    header = "### {0} (awarded {1}/{2})".format(score.label, score.awarded, score.base_value)
    if not score.votes:
        return ["", header, "_No votes recorded._"]
    return ["", header, *_vote_entries(score.votes)]


def render_appendix(scores: list[ElementScore]) -> list[str]:
    """Render a per-element judge vote appendix when any panel data exists."""
    evidence_scores = [score for score in scores if score.kind == _EVIDENCE_KIND]
    if not evidence_scores:
        return []
    lines = ["## Witness appendix"]
    for score in evidence_scores:
        lines.extend(_element_section(score))
    return lines
