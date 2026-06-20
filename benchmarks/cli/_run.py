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
    """Result of one iteration, bundled to keep local-variable counts low.

    ``report`` is ``None`` when the iteration raised; ``error`` then carries a
    one-line ``Type: message`` summary so the batch can keep going while still
    surfacing the failure in the progress log.
    """

    scenario: _scenarios.Scenario
    iteration: int
    report: _scores.ScenarioReport | None
    error: str | None = None


async def _run_one(
    scenario: _scenarios.Scenario,
    iteration: int,
    options: RunOptions,
) -> _CompletedIteration:
    """Run one iteration, converting any failure into a recorded outcome.

    A scripted turn that short-circuits without narration (e.g. the Director
    returns a clarification question, bypassing the Narrator) makes the harness
    raise ``IndexError``. Isolating it here keeps one bad scenario from aborting
    the whole batch — and the ``benchmark-baseline`` artifact upload with it.
    """
    # ``except Exception`` deliberately lets ``asyncio.CancelledError`` (a
    # ``BaseException`` since 3.8) propagate, so task cancellation is never eaten.
    try:
        report = await run_scenario_once(scenario, options=options)
    except Exception as exc:
        error = "{0}: {1}".format(type(exc).__name__, exc)
        return _CompletedIteration(scenario=scenario, iteration=iteration, report=None, error=error)
    return _CompletedIteration(scenario=scenario, iteration=iteration, report=report)


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
        yield await _run_one(scenario, iteration, options)


def _record_failure(done: _CompletedIteration) -> None:
    """Emit a one-line FAILED marker for an iteration that raised."""
    line = "[{0}] iter {1}: FAILED — {2}\n".format(done.scenario.id, done.iteration, done.error)
    sys.stdout.write(line)


def _record_iteration(done: _CompletedIteration) -> None:
    """Write archive files and emit the per-iteration progress line."""
    if done.report is None:
        _record_failure(done)
        return
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


async def _collect_reports(
    jobs: list[tuple[_scenarios.Scenario, int]],
    ctx: RunContext,
) -> tuple[list[_scores.ScenarioReport], int]:
    """Drive every iteration, returning (surviving reports, failure count)."""
    completed: list[_scores.ScenarioReport] = []
    failures = 0
    async for done in _iterate_runs(jobs, ctx):
        _record_iteration(done)
        if done.report is None:
            failures += 1
        else:
            completed.append(done.report)
    return completed, failures


async def run_command(args: argparse.Namespace) -> int:
    """Execute the ``run`` subcommand."""
    ctx = build_context(args)
    completed, failures = await _collect_reports(expand_jobs(args), ctx)
    aggregates = finalise_aggregates(completed, ctx.sha)
    print_summary_table(aggregates)
    # --no-compare keeps its documented "always exits 0" contract (ADR-0002): the
    # observational baseline run on main must stay green so its artifact is found.
    if args.no_compare:
        return 0
    # In gate mode a crashed scenario is as much a failure as a regression.
    if failures:
        return 1
    return auto_compare_exit_code(args, aggregates)
