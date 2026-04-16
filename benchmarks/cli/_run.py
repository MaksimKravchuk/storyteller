"""Implementation of the ``benchmarks run`` subcommand."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import AsyncIterator

from benchmarks.cli._jobs import RunContext, build_context, expand_jobs
from benchmarks.cli._summary import RunRow, print_summary_table
from benchmarks.cli._writer import Writer, default_writer
from benchmarks.harness.archive import write_report
from benchmarks.harness.runner import RunOptions, run_scenario_once
from benchmarks.harness.types._scenarios import Scenario
from benchmarks.harness.types._scores import ScenarioReport


@dataclass(frozen=True)
class _CompletedIteration:
    """Result of one iteration, bundled to keep local-variable counts low."""

    scenario: Scenario
    iteration: int
    report: ScenarioReport


async def _iterate_runs(
    jobs: list[tuple[Scenario, int]],
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


def _record_iteration(done: _CompletedIteration, writer: Writer) -> RunRow:
    """Write archive files, emit the iteration line, and build the summary row."""
    _, md_path = write_report(done.report)
    writer(
        "[{0}] iter {1}: {2}/{3} — wrote {4}".format(
            done.scenario.id,
            done.iteration,
            done.report.total_awarded,
            done.report.total_base,
            md_path,
        ),
    )
    return RunRow(
        scenario_id=done.scenario.id,
        iteration=done.iteration,
        awarded=done.report.total_awarded,
        base=done.report.total_base,
    )


async def run_command(args: argparse.Namespace, writer: Writer = default_writer) -> int:
    """Execute the ``run`` subcommand."""
    ctx = build_context(args)
    jobs = expand_jobs(args)
    rows = [_record_iteration(done, writer) async for done in _iterate_runs(jobs, ctx)]
    print_summary_table(rows, writer=writer)
    return 0
