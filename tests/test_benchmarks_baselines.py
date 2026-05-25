"""Unit tests for the pinned-baseline reader/writer."""

from __future__ import annotations

import json

import allure
import pytest

from benchmarks.harness import baselines
from benchmarks.harness.types._aggregates import ElementPassRate, PinnedBaseline, ScenarioAggregate


def _aggregate(scenario_id: str = "s1") -> ScenarioAggregate:
    return ScenarioAggregate(
        scenario_id=scenario_id,
        scenario_label=scenario_id,
        iterations=3,
        total_base=10,
        mean_awarded=7.0,
        min_awarded=6,
        max_awarded=8,
        element_pass_rates=[
            ElementPassRate(element_id="e1", label="recall", base_value=3, passes=2, iterations=3),
        ],
        iteration_totals=[6, 7, 8],
        stdev_awarded=0.81,
    )


def _baseline(scenario_id: str = "s1", *, noise_floor_stdev: float = 0.5) -> PinnedBaseline:
    return PinnedBaseline(
        aggregate=_aggregate(scenario_id),
        baselined_at="2026-05-25T12:00:00+00:00",
        engine_git_sha="deadbee1",
        engine_models={"director_model": "gpt-5.4-mini"},
        iterations=3,
        noise_floor_stdev=noise_floor_stdev,
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestBaselinesRoundTrip:
    @allure.story("Pinned baselines")
    @allure.title("write_baseline + read_baseline preserves every field including stdev")
    def test_round_trip_preserves_fields(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)

        path = baselines.write_baseline(_baseline())
        loaded = baselines.read_baseline("s1")

        assert path == tmp_path / "s1.json"
        assert loaded is not None
        assert loaded.engine_git_sha == "deadbee1"
        assert loaded.noise_floor_stdev == pytest.approx(0.5)
        assert loaded.aggregate.scenario_id == "s1"
        assert loaded.aggregate.stdev_awarded == pytest.approx(0.81)
        assert loaded.aggregate.element_pass_rates[0].label == "recall"
        assert loaded.engine_models == {"director_model": "gpt-5.4-mini"}

    @allure.story("Pinned baselines")
    @allure.title("read_baseline returns None when no baseline has been pinned for the scenario")
    def test_read_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)

        assert baselines.read_baseline("never_pinned") is None

    @allure.story("Pinned baselines")
    @allure.title("list_baselines enumerates only scenarios with a .json file, sorted")
    def test_list_sorted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)

        baselines.write_baseline(_baseline("zeta"))
        baselines.write_baseline(_baseline("alpha"))
        baselines.write_baseline(_baseline("mu"))

        assert baselines.list_baselines() == ["alpha", "mu", "zeta"]

    @allure.story("Pinned baselines")
    @allure.title("baseline_path uses the canonical <scenario>.json layout")
    def test_baseline_path_layout(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)

        assert baselines.baseline_path("my_scenario") == tmp_path / "my_scenario.json"

    @allure.story("Pinned baselines")
    @allure.title("baselines_dir creates and returns the package-level baselines directory")
    def test_baselines_dir_is_under_package(self):
        directory = baselines.baselines_dir()

        assert directory.is_dir()
        assert directory.name == "baselines"
        # parent.parent of this module's __file__ is `benchmarks/`; so the dir lives there.
        assert directory.parent.name == "benchmarks"

    @allure.story("Pinned baselines")
    @allure.title("write_baseline stamps the metadata header at top level (not nested in aggregate)")
    def test_metadata_header_is_top_level(self, tmp_path, monkeypatch):
        monkeypatch.setattr(baselines, "baselines_dir", lambda: tmp_path)

        path = baselines.write_baseline(_baseline(noise_floor_stdev=1.25))
        payload = json.loads(path.read_text(encoding="utf-8"))

        assert set(payload) >= {
            "baselined_at",
            "engine_git_sha",
            "engine_models",
            "iterations",
            "noise_floor_stdev",
            "aggregate",
        }
        assert payload["noise_floor_stdev"] == pytest.approx(1.25)
        # noise_floor_stdev belongs to the baseline, not the aggregate
        assert "noise_floor_stdev" not in payload["aggregate"]
