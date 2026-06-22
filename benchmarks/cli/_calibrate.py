"""Implementation of the ``benchmarks calibrate`` subcommand.

Calibrate runs N iterations per scenario, computes the per-scenario stdev, and
writes ``benchmarks/baselines/.calibration.json`` so the operator can pin
baselines with a noise floor that reflects real engine variance.

Calibrate is intentionally opt-in (CLI-only, never on CI) — it hits paid LLMs.
"""

from __future__ import annotations

import argparse
import sys

from benchmarks.cli._calibrate_drift import compute_drift_table, format_drift_table, has_drift_alert
from benchmarks.cli._calibrate_io import CalibrationEntry, read_calibration
from benchmarks.cli._calibrate_persist import CalibrationResult, persist_calibration
from benchmarks.cli._jobs import RunContext, build_context, expand_jobs
from benchmarks.harness.aggregate import aggregate_reports
from benchmarks.harness.runner import RunOptions, run_scenario_once
from benchmarks.harness.types._scenarios import Scenario
from benchmarks.harness.types._scores import ScenarioReport


async def _run_one_job(scenario: Scenario, iteration: int, ctx: RunContext) -> ScenarioReport | None:
    """Run one (scenario, iteration) job, isolating any failure as ``None``.

    A scripted turn that short-circuits without narration (e.g. the Director
    returns a clarification question, bypassing the Narrator) makes the harness
    raise ``IndexError``. Mirroring the ``run`` subcommand, we isolate it here so
    one flaky iteration cannot abort the whole noise-floor pass and leave
    ``.calibration.json`` unwritten.
    """
    options = RunOptions(
        cfg=ctx.cfg,
        iteration=iteration,
        panel_overrides=ctx.overrides,
        max_judges=ctx.max_judges,
        engine_git_sha=ctx.sha,
    )
    # ``except Exception`` deliberately lets ``asyncio.CancelledError`` (a
    # ``BaseException`` since 3.8) propagate, so task cancellation is never eaten.
    try:
        return await run_scenario_once(scenario, options=options)
    except Exception as exc:
        line = "[{0}] calibrate iter {1}: FAILED — {2}: {3}\n".format(scenario.id, iteration, type(exc).__name__, exc)
        sys.stdout.write(line)
        return None


async def _run_scenarios(jobs: list[tuple[Scenario, int]], ctx: RunContext) -> list[ScenarioReport]:
    """Run every (scenario, iteration) pair sequentially, returning surviving reports."""
    reports: list[ScenarioReport] = []
    pending = list(jobs)
    while pending:
        scenario, iteration = pending.pop(0)
        report = await _run_one_job(scenario, iteration, ctx)
        if report is not None:
            reports.append(report)
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


def _report_drift(
    old_entries: dict[str, CalibrationEntry],
    calibration_results: list[CalibrationResult],
) -> int:
    """Compare old calibration entries against fresh results; return exit code."""
    drift_rows = compute_drift_table(old_entries, calibration_results)
    sys.stdout.write(format_drift_table(drift_rows))
    return 1 if has_drift_alert(drift_rows) else 0


async def calibrate_command(args: argparse.Namespace) -> int:
    """Execute the ``calibrate`` subcommand."""
    ctx = build_context(args)
    old_entries = read_calibration() if args.compare_to_baselines else {}
    reports = await _run_scenarios(expand_jobs(args), ctx)
    calibration_results = build_calibration_results(reports, ctx)
    persist_calibration(calibration_results)
    if args.compare_to_baselines:
        return _report_drift(old_entries, calibration_results)
    return 0
