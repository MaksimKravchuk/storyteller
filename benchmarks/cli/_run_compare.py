"""Post-run auto-compare wiring for the ``benchmarks run`` subcommand.

Kept separate from :mod:`benchmarks.cli._run` so the runner module stays
focused on iteration mechanics; this module owns the verdict formatting,
ratchet, and exit-code decision.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from benchmarks.cli import _auto_compare
from benchmarks.harness import baselines
from benchmarks.harness.types._aggregates import PinnedBaseline, ScenarioAggregate

_VERDICT_LINE = "[auto-compare] {0}: {1}  (baseline={2:.2f} → current={3:.2f}, Δ/noise={4:.2f})\n"
_RATCHET_LINE = "[auto-compare] ratcheted {0} → {1}\n"


def _format_verdict(verdict: _auto_compare.Verdict) -> str:
    """Format one verdict for the post-run summary."""
    return _VERDICT_LINE.format(
        verdict.scenario_id,
        verdict.classification,
        verdict.baseline_mean,
        verdict.current_mean,
        verdict.delta_vs_noise_floor,
    )


def _aggregates_by_id(aggregates: list[ScenarioAggregate]) -> dict[str, ScenarioAggregate]:
    """Index aggregates by scenario id."""
    return {aggregate.scenario_id: aggregate for aggregate in aggregates}


def _ratchet_one(
    verdict: _auto_compare.Verdict,
    aggregate: ScenarioAggregate,
    baseline: PinnedBaseline,
) -> None:
    """Write a refreshed baseline JSON when the ratchet predicate fires."""
    if not _auto_compare.should_ratchet(verdict, baseline, aggregate):
        return
    refreshed = PinnedBaseline(
        aggregate=aggregate,
        baselined_at=datetime.now(timezone.utc).isoformat(),
        engine_git_sha=baseline.engine_git_sha,
        engine_models=dict(baseline.engine_models),
        iterations=aggregate.iterations,
        noise_floor_stdev=baseline.noise_floor_stdev,
    )
    path = baselines.write_baseline(refreshed)
    sys.stdout.write(_RATCHET_LINE.format(verdict.scenario_id, path))


def _maybe_ratchet(
    verdicts: list[_auto_compare.Verdict],
    aggregates: list[ScenarioAggregate],
) -> None:
    """Apply ``_ratchet_one`` to each improvement verdict that has a baseline."""
    index = _aggregates_by_id(aggregates)
    for verdict in verdicts:
        if verdict.classification != "improvement":
            continue
        baseline = baselines.read_baseline(verdict.scenario_id)
        aggregate = index.get(verdict.scenario_id)
        if baseline is None or aggregate is None:
            continue
        _ratchet_one(verdict, aggregate, baseline)


def auto_compare_exit_code(
    args: argparse.Namespace,
    aggregates: list[ScenarioAggregate],
) -> int:
    """Run auto-compare, print verdicts, optionally ratchet; return 0 or 1."""
    verdicts = _auto_compare.evaluate(aggregates)
    for verdict in verdicts:
        sys.stdout.write(_format_verdict(verdict))
    if args.update_baselines_on_improvement:
        _maybe_ratchet(verdicts, aggregates)
    return int(_auto_compare.any_regression(verdicts))
