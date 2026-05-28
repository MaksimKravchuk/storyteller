"""Narrative quality report model and markdown renderer."""

from __future__ import annotations

from dataclasses import dataclass

_AVERAGE_PRECISION = 2


@dataclass(frozen=True)
class RubricScore:
    """One judge score for a narrative-quality rubric."""

    rubric: str
    score: int
    reasoning: str
    issues: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeReport:
    """Complete narrative-quality report returned by the judge."""

    model: str
    scores: tuple[RubricScore, ...]

    @property
    def average(self) -> float:
        """Return the arithmetic mean score, or zero when empty."""
        if not self.scores:
            return 0
        return sum(rubric_score.score for rubric_score in self.scores) / len(self.scores)


def render_markdown_report(report: NarrativeReport, setting: str) -> str:
    """Render a human-readable markdown report for Allure/CI artifacts."""
    lines = [
        "# Narrative Quality Report",
        "",
        f"- Setting: `{setting}`",
        f"- Judge model: `{report.model}`",
        "- Average score: **{0}/10**".format(_format_average(report.average)),
        "",
        "## Scores",
    ]
    for score in report.scores:
        lines.extend(_rubric_lines(score))
    issues = _collect_issue_lines(report)
    if issues:
        lines.extend(["", "## Issues", *issues])
    return "\n".join(lines)


def _rubric_lines(score: RubricScore) -> list[str]:
    return [
        "",
        f"### {score.rubric}: {score.score}/10",
        "",
        score.reasoning,
    ]


def _format_average(score: float) -> str:
    return format(score, f".{_AVERAGE_PRECISION}f")


def _collect_issue_lines(report: NarrativeReport) -> list[str]:
    lines: list[str] = []
    for score in report.scores:
        for issue in score.issues:
            lines.append(f"- **{score.rubric}:** {issue}")
    return lines
