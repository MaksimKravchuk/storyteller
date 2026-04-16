"""Opt-in pytest wrappers around the benchmark harness.

These tests are marked ``benchmark`` and excluded from the default
pytest run via ``addopts = "-m 'not db and not benchmark'"`` in
``pyproject.toml``. Invoke explicitly with:

    uv run pytest tests/benchmarks -m benchmark -v

Each test runs one scenario once and writes a JSON + markdown artefact
to ``benchmarks/results/``. The tests assert only that the harness
completed end-to-end; rubric scores themselves are surfaced via the
artefacts for humans to review.
"""

from __future__ import annotations

import pytest

from benchmarks.harness.archive import current_git_sha, write_report
from benchmarks.harness.runner import run_scenario_once
from benchmarks.scenarios._registry import ALL_SCENARIOS
from config import load_config


@pytest.mark.benchmark
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=lambda scenario: scenario.id)
async def test_scenario_end_to_end(scenario):
    """Run one scenario end-to-end and persist the report."""
    cfg = load_config()
    report = await run_scenario_once(
        scenario,
        cfg=cfg,
        iteration=0,
        engine_git_sha=current_git_sha(),
    )
    json_path, md_path = write_report(report)
    assert json_path.is_file()
    assert md_path.is_file()
    assert report.total_base > 0
    assert len(report.captured_turns) == len(scenario.script)
