"""Unit tests for the ``benchmarks pin`` subcommand."""

from __future__ import annotations

import argparse
import json

import allure
import pytest

from benchmarks.cli import _calibrate_io, _pin
from benchmarks.harness import baselines
from benchmarks.harness.aggregate_archive import write_aggregate
from benchmarks.harness.types._aggregates import ElementPassRate, ScenarioAggregate


def _aggregate_payload(*, scenario_id: str = "memory_follow_up_marcus", stdev: float = 0.75) -> dict:
    return {
        "scenario_id": scenario_id,
        "scenario_label": scenario_id,
        "iterations": 3,
        "total_base": 10,
        "mean_awarded": 7.5,
        "min_awarded": 7,
        "max_awarded": 8,
        "stdev_awarded": stdev,
        "iteration_totals": [7, 7, 8],
        "element_pass_rates": [
            {
                "element_id": "e1",
                "label": "recall",
                "base_value": 3,
                "passes": 2,
                "iterations": 3,
            },
        ],
        "engine_git_sha": "deadbee1",
        "engine_models": {"director_model": "gpt-5.4-mini"},
    }


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestPinCommand:
    @allure.story("Pin baseline")
    @allure.title("pin copies the aggregate into baselines/<scenario>.json with metadata header")
    def test_writes_baseline_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        aggregate_path = tmp_path / "src.json"
        aggregate_path.write_text(json.dumps(_aggregate_payload()), encoding="utf-8")
        args = argparse.Namespace(
            scenario_id="memory_follow_up_marcus",
            from_path=str(aggregate_path),
        )

        exit_code = _pin.pin_command(args)

        assert exit_code == 0
        baseline = baselines.read_baseline("memory_follow_up_marcus")
        assert baseline is not None
        assert baseline.engine_git_sha == "deadbee1"
        assert baseline.aggregate.mean_awarded == pytest.approx(7.5)
        # When calibration is absent, noise floor defaults to the aggregate's stdev
        assert baseline.noise_floor_stdev == pytest.approx(0.75)
        assert "memory_follow_up_marcus" in baselines.list_baselines()

    @allure.story("Pin baseline")
    @allure.title("pin prefers the calibration file's stdev for noise_floor_stdev when present")
    def test_prefers_calibration_noise_floor(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        # Seed calibration with a deliberately different stdev
        _calibrate_io.write_calibration(
            {
                "memory_follow_up_marcus": _calibrate_io.CalibrationEntry(
                    mean=7.5,
                    stdev=1.25,
                    iterations=5,
                    engine_git_sha="deadbee1",
                    models={"director_model": "gpt-5.4-mini"},
                ),
            },
        )
        aggregate_path = tmp_path / "src.json"
        aggregate_path.write_text(json.dumps(_aggregate_payload(stdev=0.1)), encoding="utf-8")
        args = argparse.Namespace(
            scenario_id="memory_follow_up_marcus",
            from_path=str(aggregate_path),
        )

        _pin.pin_command(args)

        baseline = baselines.read_baseline("memory_follow_up_marcus")
        assert baseline is not None
        # Calibration's 1.25 wins over aggregate's 0.1
        assert baseline.noise_floor_stdev == pytest.approx(1.25)

    @allure.story("Pin baseline")
    @allure.title("pin rejects an aggregate whose scenario_id does not match the target")
    def test_rejects_scenario_mismatch(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        aggregate_path = tmp_path / "src.json"
        aggregate_path.write_text(json.dumps(_aggregate_payload(scenario_id="other_scenario")), encoding="utf-8")
        args = argparse.Namespace(scenario_id="memory_follow_up_marcus", from_path=str(aggregate_path))

        with pytest.raises(ValueError, match="does not match"):
            _pin.pin_command(args)

    @allure.story("Pin baseline")
    @allure.title("pin raises FileNotFoundError when the aggregate path does not exist")
    def test_missing_source_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        args = argparse.Namespace(scenario_id="x", from_path=str(tmp_path / "missing.json"))

        with pytest.raises(FileNotFoundError, match="Aggregate not found"):
            _pin.pin_command(args)

    @allure.story("Pin baseline")
    @allure.title("pin preserves engine_models written by the real write_aggregate pipeline")
    def test_engine_models_round_trip_from_write_aggregate(self, tmp_path, monkeypatch):
        # Consumer-seam test: pin must read engine_models from a *real* aggregate
        # JSON file produced by write_aggregate(...), not a hand-spelled payload.
        monkeypatch.setattr("benchmarks.harness.archive.results_dir", lambda: tmp_path)
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)
        aggregate = ScenarioAggregate(
            scenario_id="memory_follow_up_marcus",
            scenario_label="memory_follow_up_marcus",
            iterations=3,
            total_base=10,
            mean_awarded=7.5,
            min_awarded=7,
            max_awarded=8,
            element_pass_rates=[
                ElementPassRate(element_id="e1", label="recall", base_value=3, passes=2, iterations=3),
            ],
            iteration_totals=[7, 7, 8],
            stdev_awarded=0.75,
        )
        json_path, _ = write_aggregate(
            aggregate,
            "deadbee1",
            engine_models={"director_model": "gpt-5.4-mini", "narrator_model": "gpt-5.4-mini"},
        )

        args = argparse.Namespace(
            scenario_id="memory_follow_up_marcus",
            from_path=str(json_path),
        )
        _pin.pin_command(args)

        baseline = baselines.read_baseline("memory_follow_up_marcus")
        assert baseline is not None
        assert baseline.engine_git_sha == "deadbee1"
        assert baseline.engine_models == {
            "director_model": "gpt-5.4-mini",
            "narrator_model": "gpt-5.4-mini",
        }
