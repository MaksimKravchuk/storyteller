"""Implementation of the ``benchmarks calibrate`` subcommand.

Calibrate runs N iterations per scenario, computes the per-scenario stdev, and
writes ``benchmarks/baselines/.calibration.json`` so the operator can pin
baselines with a noise floor that reflects real engine variance.

Calibrate is intentionally opt-in (CLI-only, never on CI) — it hits paid LLMs.
"""

from __future__ import annotations

import argparse

from benchmarks.cli._calibrate_persist import CalibrationResult, persist_calibration
from benchmarks.cli._jobs import RunContext, build_context, expand_jobs
from benchmarks.harness.aggregate import aggregate_reports
from benchmarks.harness.runner import RunOptions, run_scenario_once
from benchmarks.harness.types._scenarios import Scenario
from benchmarks.harness.types._scores import ScenarioReport


async def _run_one_job(scenario: Scenario, iteration: int, ctx: RunContext) -> ScenarioReport:
    """Run one (scenario, iteration) job and return its report."""
    options = RunOptions(
        cfg=ctx.cfg,
        iteration=iteration,
        panel_overrides=ctx.overrides,
        max_judges=ctx.max_judges,
        engine_git_sha=ctx.sha,
    )
    return await run_scenario_once(scenario, options=options)


async def _run_scenarios(jobs: list[tuple[Scenario, int]], ctx: RunContext) -> list[ScenarioReport]:
    """Run every (scenario, iteration) pair sequentially, returning all reports."""
    reports: list[ScenarioReport] = []
    pending = list(jobs)
    while pending:
        scenario, iteration = pending.pop(0)
        reports.append(await _run_one_job(scenario, iteration, ctx))
    return reports


def _group_by_scenario(reports: list[ScenarioReport]) -> dict[str, list[ScenarioReport]]:
    """Group per-iteration reports by scenario id, preserving first-seen order."""
    grouped: dict[str, list[ScenarioReport]] = {}
    for report in reports:
        grouped.setdefault(report.scenario_id, []).append(report)
    return grouped


def build_calibration_results(reports: list[ScenarioReport], ctx: RunContext) -> list[CalibrationResult]:
    """Turn a flat report list into one :class:`CalibrationResult` per scenario."""
    head_models = reports[0].engine_models if reports else {}
    return [
        CalibrationResult(
            scenario_id=scenario_id,
            aggregate=aggregate_reports(scenario_reports),
            engine_git_sha=ctx.sha,
            engine_models=dict(head_models),
        )
        for scenario_id, scenario_reports in _group_by_scenario(reports).items()
    ]


async def calibrate_command(args: argparse.Namespace) -> int:
    """Execute the ``calibrate`` subcommand."""
    ctx = build_context(args)
    jobs = expand_jobs(args)
    reports = await _run_scenarios(jobs, ctx)
    calibration_results = build_calibration_results(reports, ctx)
    persist_calibration(calibration_results)
    return 0
