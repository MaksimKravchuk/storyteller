"""Implementation of the offline ``benchmarks bayes-report`` subcommand.

Reads current ``*_aggregate.json`` files from a results directory, compares each
against its git-tracked pinned baseline, and prints graded Bayesian verdicts plus
a pooled portfolio-bias line. Pure file IO — no engine run, no LLM calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmarks.cli._bayes_format import format_portfolio_line, format_scenario_block
from benchmarks.harness import baselines
from benchmarks.harness._baselines_codec import aggregate_to_dict
from benchmarks.harness.bayes._report import (
    DEFAULT_ROPE,
    portfolio_verdict,
    verdict_for_scenario,
)
from benchmarks.harness.bayes._types import ScenarioVerdict


def _write(line: str) -> None:
    sys.stdout.write("{0}\n".format(line))


def _verdict_for(current: dict, rope: float) -> ScenarioVerdict | None:
    """Build a scenario verdict against the pinned baseline, or None when unpinned."""
    baseline = baselines.read_baseline(current["scenario_id"])
    if baseline is None:
        _write("[bayes] {0}: no pinned baseline — skipped".format(current["scenario_id"]))
        return None
    return verdict_for_scenario(
        aggregate_to_dict(baseline.aggregate),
        current,
        noise_floor_stdev=baseline.noise_floor_stdev,
        rope=rope,
    )


def _collect_verdicts(results_dir: Path, rope: float) -> list[ScenarioVerdict]:
    """Compute one verdict per current aggregate file, printing each block."""
    verdicts: list[ScenarioVerdict] = []
    for path in sorted(results_dir.glob("*_aggregate.json")):
        current = json.loads(path.read_text(encoding="utf-8"))
        verdict = _verdict_for(current, rope)
        if verdict is None:
            continue
        verdicts.append(verdict)
        for line in format_scenario_block(verdict):
            _write(line)
    return verdicts


def bayes_report_command(args: argparse.Namespace) -> int:
    """Execute the ``bayes-report`` subcommand."""
    rope = DEFAULT_ROPE if args.rope is None else args.rope
    results_dir = Path(args.results)
    if not results_dir.is_dir():
        sys.stderr.write("Results directory not found: {0}\n".format(args.results))
        return 1
    verdicts = _collect_verdicts(results_dir, rope)
    if verdicts:
        _write("")
        _write(format_portfolio_line(portfolio_verdict(verdicts, rope=rope)))
    return 0
