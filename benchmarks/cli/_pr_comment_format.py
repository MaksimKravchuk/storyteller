"""Top-level markdown assembly for the ``benchmarks pr-comment`` subcommand.

Composes the advisory PR comment from precomputed verdicts: a one-line headline
badge, the pooled portfolio line, the per-scenario summary table, collapsible
per-element / glossary sections, and the narration diff. Pure and side-effect
free — all IO and verdict computation live in ``benchmarks.cli._pr_comment``.
"""

from __future__ import annotations

from benchmarks.cli._auto_compare import Verdict
from benchmarks.cli._pr_comment_elements import format_elements_section, format_glossary
from benchmarks.cli._pr_comment_rows import ScenarioSummary, format_summary_table
from benchmarks.harness.bayes._types import PortfolioVerdict

_HEADING = "## 🎭 Benchmark comparison (previous main → this PR)"

_BADGE_REGRESSION = "🔴 Regression detected"
_BADGE_IMPROVEMENT = "🟢 Improvement"
_BADGE_CLEAN = "✅ No regression"
_BADGE_NO_BASELINE = "⚪ No pinned baselines yet"
_BADGE_NO_RESULTS = "⚪ No results produced"
_NO_BASELINE = "no_baseline"

_PORTFOLIO_LINE = (
    "**Portfolio ({count} scenarios):** ΣΔ {mean:+.2f} (95% CI {lo:+.2f} … {hi:+.2f}) · "
    "P(suite worse) {reg:.0%} · P(suite better) {imp:.0%}"
)
_NO_PORTFOLIO = "_No pinned baselines to pool — portfolio verdict unavailable._"

_FOOTER = (
    "_Advisory only — this check never blocks the merge (ADR-0002 / ADR-0009). "
    "Full results for both versions are attached as workflow artifacts._"
)


def _badge(verdicts: list[Verdict]) -> str:
    """Pick the headline badge from the worst-case classification across scenarios."""
    if not verdicts:
        return _BADGE_NO_RESULTS
    classes = {verdict.classification for verdict in verdicts}
    if "regression" in classes:
        return _BADGE_REGRESSION
    if classes == {_NO_BASELINE}:
        return _BADGE_NO_BASELINE
    if "improvement" in classes:
        return _BADGE_IMPROVEMENT
    return _BADGE_CLEAN


def format_headline(verdicts: list[Verdict]) -> str:
    """Render the heading line with its verdict badge."""
    return "{0} — {1}".format(_HEADING, _badge(verdicts))


def format_portfolio(portfolio: PortfolioVerdict | None) -> str:
    """Render the pooled portfolio-bias line."""
    if portfolio is None:
        return _NO_PORTFOLIO
    total = portfolio.total
    return _PORTFOLIO_LINE.format(
        count=portfolio.scenario_count,
        mean=total.delta_mean,
        lo=total.ci_low,
        hi=total.ci_high,
        reg=total.p_regression,
        imp=total.p_improvement,
    )


def format_comment(
    summaries: list[ScenarioSummary],
    portfolio: PortfolioVerdict | None,
    narration_markdown: str,
) -> str:
    """Assemble the full advisory PR comment as a single markdown document."""
    verdicts = [summary.verdict for summary in summaries]
    blocks = [
        format_headline(verdicts),
        "",
        format_portfolio(portfolio),
        "",
        format_summary_table(summaries),
        "",
        format_elements_section(summaries),
        "",
        format_glossary(),
        "",
        narration_markdown,
        "",
        _FOOTER,
    ]
    return "\n".join(blocks)
