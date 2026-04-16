"""Opt-in pytest wrappers around the benchmark harness.

Excluded from default CI via the ``benchmark`` marker. Invoke explicitly:

    uv run pytest tests/benchmarks -m benchmark -v
"""

from __future__ import annotations

import pytest

from benchmarks.harness.archive import current_git_sha, write_report
from benchmarks.harness.runner import RunOptions, run_scenario_once
from benchmarks.scenarios._registry import ALL_SCENARIOS
from config import load_config


@pytest.mark.benchmark
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=lambda scenario: scenario.id)
async def test_scenario_end_to_end(scenario):
    """Run one scenario end-to-end and persist the report."""
    options = RunOptions(
        cfg=load_config(),
        iteration=0,
        engine_git_sha=current_git_sha(),
    )
    report = await run_scenario_once(scenario, options=options)
    json_path, md_path = write_report(report)
    assert json_path.is_file()
    assert md_path.is_file()
    assert report.total_base > 0
    assert len(report.captured_turns) == len(scenario.script)
