"""Disk → view-model scoring for the ``benchmarks pr-comment`` subcommand.

Scores the current run's aggregates against pinned baselines (frequentist
auto-compare plus the graded Bayesian verdict) and builds the narration diff.
Pure file IO — no engine run, no LLM calls.
"""

from __future__ import annotations

from pathlib import Path

from benchmarks.cli._auto_compare import evaluate
from benchmarks.cli._narration_diff import build_turn_index
from benchmarks.cli._narration_diff_format import format_report
from benchmarks.cli._pr_comment_rows import ScenarioSummary
from benchmarks.cli._results_aggregates import latest_aggregates
from benchmarks.cli._scenario_verdict import bayes_verdict_for
from benchmarks.harness._baselines_codec import aggregate_from_dict
from benchmarks.harness.bayes._report import portfolio_verdict
from benchmarks.harness.bayes._types import PortfolioVerdict


def gather_summaries(results_dir: Path, rope: float) -> list[ScenarioSummary]:
    """Pair each scenario's frequentist verdict with its Bayesian drill-down."""
    aggregates = latest_aggregates(results_dir)
    verdicts = evaluate([aggregate_from_dict(payload) for payload in aggregates])
    return [
        ScenarioSummary(verdict=verdict, bayes=bayes_verdict_for(current, rope))
        for verdict, current in zip(verdicts, aggregates)
    ]


def pool_portfolio(summaries: list[ScenarioSummary], rope: float) -> PortfolioVerdict | None:
    """Pool the Bayesian scenario verdicts, or None when nothing is pinned."""
    scenarios = [summary.bayes for summary in summaries if summary.bayes is not None]
    if not scenarios:
        return None
    return portfolio_verdict(scenarios, rope=rope)


def narration_markdown(previous: str, current_dir: Path) -> str:
    """Render the narration diff, degrading gracefully when previous is absent."""
    previous_root = Path(previous)
    previous_index = build_turn_index(previous_root) if previous and previous_root.exists() else {}
    return format_report(previous_index, build_turn_index(current_dir))
