"""Regression: one failing scenario must not abort the whole ``run`` batch.

A scripted turn can legitimately produce no narration (the Director short-circuits
with a clarification question, bypassing the Narrator), which makes the harness
raise ``IndexError: Narrator capture buffer is empty``. Before this guard that
exception aborted the entire multi-scenario run — and on ``main`` it took down the
``benchmark-baseline`` workflow, leaving the PR gate serving a stale artifact.

A second regression guarded here: a crashed scenario must not suppress the
``[auto-compare]`` verdict lines for the scenarios that *did* produce aggregates
(the PR gate greps those lines for its Score verdict section).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from types import SimpleNamespace

import allure
import pytest

from benchmarks.cli import _run


@dataclass
class _FakeScenario:
    id: str


@dataclass
class _FakeReport:
    total_awarded: int = 5
    total_base: int = 10


class _FinaliseRecorder:
    """Module-level stand-in for ``finalise_aggregates`` that records its input."""

    def __init__(self) -> None:
        self.reports: list = []

    def __call__(self, reports, sha):
        self.reports = list(reports)
        return ["AGG"]


class _AutoCompareRecorder:
    """Stand-in for ``auto_compare_exit_code`` that records whether it ran."""

    def __init__(self) -> None:
        self.aggregates = None

    def __call__(self, args, aggregates):
        self.aggregates = aggregates
        return 0


async def _fake_run_scenario_once(scenario, *, options):
    """Raise for the ``bad`` scenario, succeed for everything else."""
    if scenario.id == "bad_scenario":
        raise IndexError("Narrator capture buffer is empty")
    return _FakeReport()


def _args(*, no_compare: bool) -> argparse.Namespace:
    return argparse.Namespace(no_compare=no_compare, update_baselines_on_improvement=False)


@pytest.fixture
def patched_run(monkeypatch):
    """Wire ``run_command`` to two scenarios — one raising, one succeeding."""
    jobs = [(_FakeScenario(id="bad_scenario"), 0), (_FakeScenario(id="good_scenario"), 0)]
    ctx = _run.RunContext(cfg=object(), overrides=None, sha="deadbeef", max_judges=3)
    finalise = _FinaliseRecorder()
    auto_compare = _AutoCompareRecorder()
    monkeypatch.setattr(_run, "build_context", lambda args: ctx)
    monkeypatch.setattr(_run, "expand_jobs", lambda args: jobs)
    monkeypatch.setattr(_run, "run_scenario_once", _fake_run_scenario_once)
    monkeypatch.setattr(_run, "write_report", lambda report: ("agg.json", "report.md"))
    monkeypatch.setattr(_run, "finalise_aggregates", finalise)
    monkeypatch.setattr(_run, "print_summary_table", lambda aggregates: None)
    monkeypatch.setattr(_run, "auto_compare_exit_code", auto_compare)
    return SimpleNamespace(finalise=finalise, auto_compare=auto_compare)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestRunScenarioIsolation:
    @allure.story("Scenario isolation")
    @allure.title("a scenario that raises is reported as FAILED but does not abort the batch")
    @pytest.mark.asyncio
    async def test_failing_scenario_does_not_abort_run(self, patched_run, capsys):
        code = await _run.run_command(_args(no_compare=True))

        out = capsys.readouterr().out
        assert "[bad_scenario] iter 0: FAILED" in out
        assert "Narrator capture buffer is empty" in out
        assert "[good_scenario] iter 0: 5/10" in out
        # The surviving scenario's report still reaches aggregation.
        assert len(patched_run.finalise.reports) == 1
        # --no-compare keeps its documented "always exits 0" contract (ADR-0002).
        assert code == 0

    @allure.story("Scenario isolation")
    @allure.title("a hard scenario failure surfaces as a non-zero exit in compare mode")
    @pytest.mark.asyncio
    async def test_compare_mode_signals_failure_via_exit_code(self, patched_run):
        code = await _run.run_command(_args(no_compare=False))

        assert code == 1

    @allure.story("Scenario isolation")
    @allure.title("auto-compare still runs for survivors even when another scenario crashed")
    @pytest.mark.asyncio
    async def test_failure_does_not_suppress_auto_compare_verdicts(self, patched_run):
        await _run.run_command(_args(no_compare=False))

        # Verdicts must still be emitted for the surviving aggregates despite the
        # crash — the PR gate's Score verdict section depends on this output.
        assert patched_run.auto_compare.aggregates == ["AGG"]
