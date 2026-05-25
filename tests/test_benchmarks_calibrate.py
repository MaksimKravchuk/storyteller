"""Unit tests for the ``benchmarks calibrate`` subcommand.

The runner loop hits paid LLMs, so these tests cover the *structure*:
report-to-CalibrationEntry translation, calibration JSON layout, and the
high-noise warning. They use synthetic reports / aggregates, never a real run.
"""

from __future__ import annotations

import argparse
import json

import allure
import pytest

from benchmarks.cli import _calibrate, _calibrate_io, _calibrate_persist
from benchmarks.cli._jobs import RunContext
from benchmarks.harness import baselines
from benchmarks.harness.types._aggregates import ScenarioAggregate
from benchmarks.harness.types._scenarios import Scenario
from benchmarks.harness.types._scores import ScenarioReport


def _report(scenario_id: str, *, awarded: int) -> ScenarioReport:
    return ScenarioReport(
        scenario_id=scenario_id,
        scenario_label=scenario_id,
        iteration=0,
        total_base=10,
        total_awarded=awarded,
        element_scores=[],
        captured_turns=[],
        panel=[],
        skipped_panel_candidates=[],
        engine_git_sha="deadbee1",
        engine_models={"director_model": "gpt-5.4-mini"},
        started_at="2026-04-20T00:00:00+00:00",
        duration_seconds=1.0,
    )


def _ctx() -> RunContext:
    return RunContext(cfg=None, overrides=None, sha="deadbee1", max_judges=None)  # type: ignore[arg-type]


class _RecordingRunner:
    """Callable awaitable runner stub that records (scenario_id, iteration)."""

    def __init__(self, captured: list[tuple[str, int]]) -> None:
        self.captured = captured

    async def __call__(self, scenario, *, options):
        self.captured.append((scenario.id, options.iteration))
        return _report(scenario.id, awarded=7)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestBuildCalibrationResults:
    @allure.story("Calibrate")
    @allure.title("build_calibration_results groups by scenario id and aggregates each group")
    def test_groups_and_aggregates(self):
        reports = [
            _report("memory", awarded=6),
            _report("memory", awarded=8),
            _report("memory", awarded=7),
            _report("narrator", awarded=5),
            _report("narrator", awarded=5),
            _report("narrator", awarded=5),
        ]

        results = _calibrate.build_calibration_results(reports, _ctx())

        by_id = {result.scenario_id: result for result in results}
        assert set(by_id) == {"memory", "narrator"}
        assert by_id["memory"].aggregate.iterations == 3
        assert by_id["memory"].aggregate.mean_awarded == pytest.approx(7.0)
        assert by_id["narrator"].aggregate.stdev_awarded == pytest.approx(float(0))
        assert by_id["memory"].engine_git_sha == "deadbee1"
        assert by_id["memory"].engine_models == {"director_model": "gpt-5.4-mini"}


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestPersistCalibration:
    @allure.story("Calibrate")
    @allure.title("persist_calibration writes a calibration JSON keyed by scenario id")
    def test_writes_calibration_json(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        results = [
            _calibrate_persist.CalibrationResult(
                scenario_id="memory",
                aggregate=ScenarioAggregate(
                    scenario_id="memory",
                    scenario_label="memory",
                    iterations=5,
                    total_base=10,
                    mean_awarded=7.2,
                    min_awarded=6,
                    max_awarded=8,
                    element_pass_rates=[],
                    iteration_totals=[6, 7, 7, 8, 8],
                    stdev_awarded=0.75,
                ),
                engine_git_sha="deadbee1",
                engine_models={"director_model": "gpt-5.4-mini"},
            ),
        ]

        _calibrate_persist.persist_calibration(results)

        path = _calibrate_io.calibration_path()
        assert path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["memory"]["stdev"] == pytest.approx(0.75)
        assert payload["memory"]["iterations"] == 5
        assert payload["memory"]["engine_git_sha"] == "deadbee1"
        assert payload["memory"]["models"] == {"director_model": "gpt-5.4-mini"}
        assert "Wrote calibration" in capsys.readouterr().out

    @allure.story("Calibrate")
    @allure.title("persist_calibration emits a high-noise warning when stdev > 0.15 * total_base")
    def test_high_noise_warning(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        results = [
            _calibrate_persist.CalibrationResult(
                scenario_id="noisy",
                aggregate=ScenarioAggregate(
                    scenario_id="noisy",
                    scenario_label="noisy",
                    iterations=5,
                    total_base=10,
                    mean_awarded=6.0,
                    min_awarded=2,
                    max_awarded=9,
                    element_pass_rates=[],
                    iteration_totals=[2, 4, 6, 8, 10],
                    stdev_awarded=3.0,  # 3.0 > 0.15 * 10 = 1.5
                ),
                engine_git_sha="deadbee1",
                engine_models={},
            ),
        ]

        _calibrate_persist.persist_calibration(results)
        out = capsys.readouterr().out

        assert "high noise" in out
        assert "--iterations 10" in out

    @allure.story("Calibrate")
    @allure.title("persist_calibration does not warn when stdev is within the noise threshold")
    def test_no_warning_when_quiet(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        results = [
            _calibrate_persist.CalibrationResult(
                scenario_id="quiet",
                aggregate=ScenarioAggregate(
                    scenario_id="quiet",
                    scenario_label="quiet",
                    iterations=5,
                    total_base=10,
                    mean_awarded=7.0,
                    min_awarded=6,
                    max_awarded=8,
                    element_pass_rates=[],
                    iteration_totals=[6, 7, 7, 7, 8],
                    stdev_awarded=0.6,  # 0.6 < 1.5
                ),
                engine_git_sha="deadbee1",
                engine_models={},
            ),
        ]

        _calibrate_persist.persist_calibration(results)
        out = capsys.readouterr().out

        assert "high noise" not in out


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestRunScenariosMocked:
    @pytest.mark.asyncio
    @allure.story("Calibrate")
    @allure.title("_run_scenarios drains the job queue sequentially via the mocked runner")
    async def test_run_scenarios_invokes_runner_per_job(self, monkeypatch):
        captured: list[tuple[str, int]] = []
        monkeypatch.setattr("benchmarks.cli._calibrate.run_scenario_once", _RecordingRunner(captured))

        # Build two scenario sentinels by subclassing Scenario.__init__ via SimpleNamespace
        scenarios = [
            type("Stub", (), {"id": "memory"})(),
            type("Stub", (), {"id": "narrator"})(),
        ]
        jobs: list[tuple[Scenario, int]] = [
            (scenarios[0], 0),
            (scenarios[0], 1),
            (scenarios[1], 0),
        ]
        reports = await _calibrate._run_scenarios(jobs, _ctx())

        assert captured == [("memory", 0), ("memory", 1), ("narrator", 0)]
        assert [report.scenario_id for report in reports] == ["memory", "memory", "narrator"]

    @pytest.mark.asyncio
    @allure.story("Calibrate")
    @allure.title("calibrate_command runs the loop, builds results, writes calibration, returns 0")
    async def test_calibrate_command_end_to_end(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        captured: list[tuple[str, int]] = []
        monkeypatch.setattr("benchmarks.cli._calibrate.run_scenario_once", _RecordingRunner(captured))
        monkeypatch.setattr(
            "benchmarks.cli._calibrate.build_context",
            lambda args: _ctx(),
        )
        sentinel = type("Stub", (), {"id": "memory"})()
        monkeypatch.setattr(
            "benchmarks.cli._calibrate.expand_jobs",
            lambda args: [(sentinel, 0), (sentinel, 1), (sentinel, 2)],
        )

        exit_code = await _calibrate.calibrate_command(
            argparse.Namespace(
                iterations=3,
                scenario=None,
                judges=None,
                max_judges=None,
                compare_to_baselines=False,
            ),
        )

        assert exit_code == 0
        payload = json.loads(_calibrate_io.calibration_path().read_text(encoding="utf-8"))
        assert "memory" in payload


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestCalibrateCommandDriftIntegration:
    @pytest.mark.asyncio
    @allure.story("Calibrate")
    @allure.title("calibrate_command reads old calibration before persisting, returns 1 on drift")
    async def test_compare_to_baselines_detects_drift(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        _calibrate_io.write_calibration(
            {
                "memory": _calibrate_io.CalibrationEntry(
                    mean=7.0,
                    stdev=2.0,
                    iterations=3,
                    engine_git_sha="deadbee1",
                    models={},
                ),
            }
        )
        monkeypatch.setattr("benchmarks.cli._calibrate.run_scenario_once", _RecordingRunner([]))
        monkeypatch.setattr("benchmarks.cli._calibrate.build_context", lambda args: _ctx())
        sentinel = type("Stub", (), {"id": "memory"})()
        monkeypatch.setattr(
            "benchmarks.cli._calibrate.expand_jobs",
            lambda args: [(sentinel, 0), (sentinel, 1), (sentinel, 2)],
        )

        exit_code = await _calibrate.calibrate_command(
            argparse.Namespace(
                iterations=3,
                scenario=None,
                judges=None,
                max_judges=None,
                compare_to_baselines=True,
            ),
        )

        assert exit_code == 1
        assert "YES" in capsys.readouterr().out


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestCalibrationIO:
    @allure.story("Calibrate")
    @allure.title("read_calibration_for returns None when no calibration file exists")
    def test_read_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)

        assert _calibrate_io.read_calibration_for("anything") is None

    @allure.story("Calibrate")
    @allure.title("write_calibration + read_calibration round-trips every entry field")
    def test_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        entries = {
            "memory": _calibrate_io.CalibrationEntry(
                mean=7.0,
                stdev=0.8,
                iterations=5,
                engine_git_sha="deadbee1",
                models={"director_model": "gpt-5.4-mini"},
            ),
        }

        _calibrate_io.write_calibration(entries)
        loaded = _calibrate_io.read_calibration()

        assert loaded["memory"].mean == pytest.approx(7.0)
        assert loaded["memory"].stdev == pytest.approx(0.8)
        assert loaded["memory"].models == {"director_model": "gpt-5.4-mini"}
