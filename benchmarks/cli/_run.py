"""Implementation of the ``benchmarks run`` subcommand."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import AsyncIterator

from benchmarks.cli._aggregate_flow import finalise_aggregates
from benchmarks.cli._jobs import RunContext, build_context, expand_jobs
from benchmarks.cli._run_compare import auto_compare_exit_code
from benchmarks.cli._summary import print_summary_table
from benchmarks.harness.archive import write_report
from benchmarks.harness.runner import RunOptions, run_scenario_once
from benchmarks.harness.types import _scenarios, _scores


@dataclass(frozen=True)
class _CompletedIteration:
    """Result of one iteration, bundled to keep local-variable counts low."""

    scenario: _scenarios.Scenario
    iteration: int
    report: _scores.ScenarioReport


async def _iterate_runs(
    jobs: list[tuple[_scenarios.Scenario, int]],
    ctx: RunContext,
) -> AsyncIterator[_CompletedIteration]:
    """Yield completed iterations in sequential order."""
    pending = list(jobs)
    while pending:
        scenario, iteration = pending.pop(0)
        options = RunOptions(
            cfg=ctx.cfg,
            iteration=iteration,
            panel_overrides=ctx.overrides,
            max_judges=ctx.max_judges,
            engine_git_sha=ctx.sha,
        )
        report = await run_scenario_once(scenario, options=options)
        yield _CompletedIteration(scenario=scenario, iteration=iteration, report=report)


def _record_iteration(done: _CompletedIteration) -> None:
    """Write archive files and emit the per-iteration progress line."""
    _, md_path = write_report(done.report)
    sys.stdout.write(
        "[{0}] iter {1}: {2}/{3} — wrote {4}\n".format(
            done.scenario.id,
            done.iteration,
            done.report.total_awarded,
            done.report.total_base,
            md_path,
        )
    )


async def run_command(args: argparse.Namespace) -> int:
    """Execute the ``run`` subcommand."""
    ctx = build_context(args)
    jobs = expand_jobs(args)
    completed: list[_scores.ScenarioReport] = []
    async for done in _iterate_runs(jobs, ctx):
        _record_iteration(done)
        completed.append(done.report)
    aggregates = finalise_aggregates(completed, ctx.sha)
    print_summary_table(aggregates)
    if args.no_compare:
        return 0
    return auto_compare_exit_code(args, aggregates)
