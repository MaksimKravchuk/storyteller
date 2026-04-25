"""Filesystem gathering for cross-set comparison."""

from __future__ import annotations

import json
from pathlib import Path

import allure

from benchmarks.model_sets import _gather


def _write_aggregate(path: Path, *, total_base: int, totals: list[int]) -> None:
    payload = {"iteration_totals": totals, "total_base": total_base, "iterations": len(totals)}
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_iter(path: Path, *, awarded: int, total_base: int, models: dict[str, str]) -> None:
    payload = {"total_awarded": awarded, "total_base": total_base, "engine_models": models}
    path.write_text(json.dumps(payload), encoding="utf-8")


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark model-set comparison")
class TestGatherBaseline:
    @allure.story("Baseline selection")
    @allure.title("When multiple baseline aggregates exist the most recent timestamp wins")
    def test_picks_most_recent_aggregate(self, tmp_path: Path) -> None:
        older = tmp_path / "2026-04-20T10-00-00_aaaaaaa_memory_follow_up_marcus_aggregate.json"
        newer = tmp_path / "2026-04-24T22-23-37_3d6410b_memory_follow_up_marcus_aggregate.json"
        _write_aggregate(older, total_base=10, totals=[1, 1, 1])
        _write_aggregate(newer, total_base=10, totals=[8, 8, 8])

        score = _gather.gather(tmp_path, "baseline", "memory_follow_up_marcus")

        assert score is not None
        assert score.iteration_totals == (8, 8, 8)

    @allure.story("Baseline selection")
    @allure.title("Returns None when no baseline aggregate is present for the scenario")
    def test_returns_none_when_absent(self, tmp_path: Path) -> None:
        assert _gather.gather(tmp_path, "baseline", "memory_follow_up_marcus") is None


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark model-set comparison")
class TestGatherSet:
    @allure.story("Set selection")
    @allure.title("Aggregate is preferred and engine_models is sourced from a sibling iter file")
    def test_prefers_aggregate_and_seeds_engine_models_from_iter(self, tmp_path: Path) -> None:
        aggregate = tmp_path / "set-economy__2026-04-24T22-23-37_3d6410b_memory_follow_up_marcus_aggregate.json"
        iter0 = tmp_path / "set-economy__2026-04-24T22-20-09_3d6410b_memory_follow_up_marcus_iter0.json"
        _write_aggregate(aggregate, total_base=10, totals=[6, 7, 8])
        _write_iter(iter0, awarded=6, total_base=10, models={"director_model": "gpt-5.4-nano"})

        score = _gather.gather(tmp_path, "economy", "memory_follow_up_marcus")

        assert score is not None
        assert score.iteration_totals == (6, 7, 8)
        assert score.engine_models == {"director_model": "gpt-5.4-nano"}

    @allure.story("Set selection")
    @allure.title("Falls back to per-iter payloads when no aggregate exists yet")
    def test_falls_back_to_iters_when_aggregate_missing(self, tmp_path: Path) -> None:
        iter0 = tmp_path / "set-economy__2026-04-24T22-20-09_3d6410b_memory_follow_up_marcus_iter0.json"
        iter1 = tmp_path / "set-economy__2026-04-24T22-21-12_3d6410b_memory_follow_up_marcus_iter1.json"
        _write_iter(iter0, awarded=6, total_base=10, models={"director_model": "gpt-5.4-nano"})
        _write_iter(iter1, awarded=7, total_base=10, models={"director_model": "gpt-5.4-nano"})

        score = _gather.gather(tmp_path, "economy", "memory_follow_up_marcus")

        assert score is not None
        assert score.iterations == 2
        assert score.iteration_totals == (6, 7)

    @allure.story("Set selection")
    @allure.title("Returns None when no archives match the (set, scenario) pair")
    def test_returns_none_when_no_archives(self, tmp_path: Path) -> None:
        assert _gather.gather(tmp_path, "economy", "memory_follow_up_marcus") is None

    @allure.story("Set selection")
    @allure.title("Other sets and other scenarios in the same dir are not picked up")
    def test_does_not_match_other_sets_or_scenarios(self, tmp_path: Path) -> None:
        other_set = tmp_path / "set-max__2026-04-24T22-23-37_3d6410b_memory_follow_up_marcus_aggregate.json"
        other_scenario = (
            tmp_path / "set-economy__2026-04-24T22-15-10_3d6410b_memory_follow_up_marcus_graph_only_aggregate.json"
        )
        _write_aggregate(other_set, total_base=10, totals=[9, 9, 9])
        _write_aggregate(other_scenario, total_base=10, totals=[2, 2, 2])

        assert _gather.gather(tmp_path, "economy", "memory_follow_up_marcus") is None
