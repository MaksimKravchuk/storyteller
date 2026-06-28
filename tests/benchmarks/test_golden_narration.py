"""No-LLM golden narration snapshot checks for benchmark scenarios."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, cast

import allure
import pytest

from benchmarks.cli._narration_diff_model import ScenarioIndex
from benchmarks.harness._golden_read import (
    DEFAULT_GOLDEN_DIR,
    compare_narration_indexes,
    load_narration_index,
    serialise_snapshot,
    snapshot_from_turns,
)
from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.scenarios._registry import ALL_SCENARIOS

pytestmark = [
    allure.epic("Benchmarks"),
    allure.feature("Golden narration snapshots"),
]


class GoldenData:
    scene_id = "scene_a"
    action_look = "look"
    old_narration = "Old stones line the road."
    new_narration = "Fresh banners hang over the road."
    exact_narration = "Exact prose."
    duration_ms = 12345


def _turn(narration: str = GoldenData.old_narration, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"index": 0, "player_action": GoldenData.action_look, "narration": narration}
    payload.update(extra)
    return payload


def _write_snapshot(root: Path, scenario_id: str, turns: list[Mapping[str, object]]) -> Path:
    path = root / "{0}.json".format(scenario_id)
    path.write_text(
        json.dumps(
            {"schema_version": 1, "scenario_id": scenario_id, "turns": turns, "element_scores": [{"awarded": 0}]},
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _write_pair(tmp_path: Path, current_turn: Mapping[str, object]) -> tuple[Path, Path]:
    golden = tmp_path / "golden"
    current = tmp_path / "current"
    golden.mkdir()
    current.mkdir()
    _write_snapshot(golden, GoldenData.scene_id, [_turn()])
    _write_snapshot(current, GoldenData.scene_id, [current_turn])
    return golden, current


def _failures(golden: Path, current: Path) -> list[str]:
    return compare_narration_indexes(load_narration_index(golden), load_narration_index(current))


def _assert_actions_match_registry(golden: ScenarioIndex) -> None:
    by_id = {scenario.id: scenario for scenario in ALL_SCENARIOS}
    for scenario_id, turns in golden.items():
        expected_actions = [turn.player_action for turn in by_id[scenario_id].script]
        actual_actions = [turn.player_action for turn in turns]
        assert actual_actions == expected_actions, scenario_id


class TestGoldenNarration:
    """No-LLM golden narration snapshot tests."""

    @allure.story("Golden snapshot loading")
    @allure.title("Golden loader extracts only per-turn narration fields from snapshot JSON")
    def test_load_index_extracts_turn_text(self, tmp_path: Path) -> None:
        _write_snapshot(tmp_path, GoldenData.scene_id, [_turn()])

        index = load_narration_index(tmp_path)

        assert list(index) == [GoldenData.scene_id]
        assert index[GoldenData.scene_id][0].index == 0
        assert index[GoldenData.scene_id][0].player_action == GoldenData.action_look
        assert index[GoldenData.scene_id][0].narration == GoldenData.old_narration

    @allure.story("Golden snapshot loading")
    @allure.title("Golden snapshots serialize only stable narration fields with canonical JSON bytes")
    def test_snapshot_excludes_volatile_fields(self) -> None:
        turn = CapturedTurn(
            index=0,
            player_action=GoldenData.action_look,
            narration=GoldenData.exact_narration,
            turn_outputs=cast(Any, {"volatile": "ignored"}),
            duration_ms=GoldenData.duration_ms,
        )

        payload = snapshot_from_turns(GoldenData.scene_id, [turn])
        serialised = serialise_snapshot(payload)

        assert payload == {
            "schema_version": 1,
            "scenario_id": GoldenData.scene_id,
            "turns": [
                {"index": 0, "player_action": GoldenData.action_look, "narration": GoldenData.exact_narration},
            ],
        }
        assert "duration_ms" not in serialised
        assert "turn_outputs" not in serialised
        assert serialised.endswith("\n")
        assert serialised.index('"narration"') < serialised.index('"player_action"')

    @allure.story("Golden snapshot comparison")
    @allure.title("Narration comparison ignores witness-panel scoring fields")
    def test_compare_ignores_panel_scores(self, tmp_path: Path) -> None:
        golden, current = _write_pair(tmp_path, _turn(turn_outputs={"changed": True}))

        assert _failures(golden, current) == []

    @allure.story("Golden snapshot comparison")
    @allure.title("Narration comparison reports an actionable unified diff when prose changes")
    def test_compare_reports_narration_diff(self, tmp_path: Path) -> None:
        golden, current = _write_pair(tmp_path, _turn(narration=GoldenData.new_narration))

        diff = _failures(golden, current)[0]

        assert all(
            part in diff
            for part in (
                "scene_a turn 0 narration differs",
                "--- golden",
                "+++ current",
                "-Old stones line the road.",
                "+Fresh banners hang over the road.",
            )
        )

    @allure.story("Golden snapshot coverage")
    @allure.title("Committed golden narration snapshots cover every registered benchmark scenario")
    def test_committed_goldens_cover_registry(self) -> None:
        if not DEFAULT_GOLDEN_DIR.exists():
            pytest.skip("Missing benchmarks/golden/<scenario_id>.json files.")

        golden = load_narration_index(DEFAULT_GOLDEN_DIR)
        if not golden:
            pytest.skip("No benchmarks/golden/<scenario_id>.json files found.")

        assert set(golden) == {scenario.id for scenario in ALL_SCENARIOS}
        assert compare_narration_indexes(golden, load_narration_index(DEFAULT_GOLDEN_DIR)) == []
        _assert_actions_match_registry(golden)
