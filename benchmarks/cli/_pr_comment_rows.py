"""The per-scenario summary table for the ``benchmarks pr-comment`` comment."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from benchmarks.cli._auto_compare import Verdict
from benchmarks.harness.bayes._types import ScenarioVerdict

_NO_BASELINE = "no_baseline"
_BLANK = "—"

_ROW_MARKER: Mapping[str, str] = MappingProxyType(
    {
        "regression": "🔴 regression",
        "improvement": "🟢 improvement",
        "noise": "✅ noise",
        "no_baseline": "⚪ no baseline",
    },
)

_TABLE_HEADER = "| Scenario | Mean (base → cur) | Δ/floor | P(reg) | Verdict |\n|---|---|---|---|---|"
_NO_ROWS = "_No scenarios scored — see job log._"


@dataclass(frozen=True)
class ScenarioSummary:
    """One scenario's frequentist verdict paired with its Bayesian drill-down."""

    verdict: Verdict
    bayes: ScenarioVerdict | None


def _mean_cell(verdict: Verdict) -> str:
    """Baseline→current mean cell (blank baseline when no pinned baseline)."""
    if verdict.classification == _NO_BASELINE:
        return "{0} → {1:.2f}".format(_BLANK, verdict.current_mean)
    return "{0:.2f} → {1:.2f}".format(verdict.baseline_mean, verdict.current_mean)


def _floor_cell(verdict: Verdict) -> str:
    """Delta-vs-noise-floor cell (blank when no pinned baseline)."""
    if verdict.classification == _NO_BASELINE:
        return _BLANK
    return "{0:+.2f}σ".format(verdict.delta_vs_noise_floor)


def _preg_cell(bayes: ScenarioVerdict | None) -> str:
    """Posterior P(regression) cell (blank when no Bayesian verdict)."""
    if bayes is None:
        return _BLANK
    return "{0:.0%}".format(bayes.total.p_regression)


def _summary_row(summary: ScenarioSummary) -> str:
    """Render one scenario's summary-table row."""
    verdict = summary.verdict
    return "| {0} | {1} | {2} | {3} | {4} |".format(
        verdict.scenario_id,
        _mean_cell(verdict),
        _floor_cell(verdict),
        _preg_cell(summary.bayes),
        _ROW_MARKER[verdict.classification],
    )


def format_summary_table(summaries: list[ScenarioSummary]) -> str:
    """Render the per-scenario verdict table."""
    if not summaries:
        return _NO_ROWS
    rows = [_TABLE_HEADER]
    rows.extend(_summary_row(summary) for summary in summaries)
    return "\n".join(rows)
