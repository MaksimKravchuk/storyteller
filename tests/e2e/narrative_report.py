"""Data shapes and markdown rendering for narrative quality reports."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RubricScore:
    """One rubric's graded result."""

    rubric: str
    score: int
    reasoning: str
    issues: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeReport:
    """Aggregate grade for one full session across every rubric."""

    model: str
    scores: tuple[RubricScore, ...]

    @property
    def average(self) -> float:
        denominator = max(len(self.scores), 1)
        return sum(rs.score for rs in self.scores) / denominator


def render_markdown_report(report: NarrativeReport, setting: str) -> str:
    """Render a PR-comment-friendly markdown summary of a narrative report."""
    judge_model = report.model
    average_line = f"**Average score:** {report.average:.1f} / 10"
    lines: list[str] = [
        "## Narrative Quality Report",
        "",
        f"**Setting:** {setting}",
        f"**Judge model:** {judge_model}",
        average_line,
        "",
        "| Rubric | Score | Summary |",
        "| --- | --- | --- |",
    ]
    for rs in report.scores:
        lines.append(_format_score_row(rs))

    issue_lines = _collect_issue_lines(report)
    if issue_lines:
        lines.append("")
        lines.append("### Issues flagged")
        lines.extend(issue_lines)

    return "\n".join(lines)


def _format_score_row(rs: RubricScore) -> str:
    rubric_name = rs.rubric.title()
    rubric_score = rs.score
    summary = _one_line(rs.reasoning)
    return f"| {rubric_name} | {rubric_score}/10 | {summary} |"


def _one_line(phrase: str) -> str:
    collapsed = " ".join(phrase.split())
    return collapsed.replace("|", r"\|")


def _collect_issue_lines(report: NarrativeReport) -> list[str]:
    issue_lines: list[str] = []
    for rs in report.scores:
        rubric_label = rs.rubric.title()
        for issue in rs.issues:
            cleaned = _one_line(issue)
            issue_lines.append(f"- **{rubric_label}:** {cleaned}")
    return issue_lines
