"""Unit tests for golden narration snapshot read/write helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace

import allure

from benchmarks.harness import golden


class _TurnOutputs:
    """Small stand-in for TurnOutputs with the model_dump contract."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def model_dump(self, *, mode: str) -> dict:
        assert mode == "json"
        return self._payload


def _turn(index: int, *, duration_ms: int = 123) -> SimpleNamespace:
    return SimpleNamespace(
        index=index,
        player_action="look around {0}".format(index),
        narration="Narration {0}".format(index),
        turn_outputs=_TurnOutputs({"wait": False, "intent": "observe"}),
        duration_ms=duration_ms,
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestGoldenSnapshots:
    @allure.story("Golden narration")
    @allure.title("write_golden_snapshot writes the canonical golden/<scenario>.json layout")
    def test_write_golden_snapshot_layout(self, tmp_path, monkeypatch):
        monkeypatch.setattr(golden, "golden_dir", lambda: tmp_path)
        scenario = SimpleNamespace(id="memory_follow_up_marcus", label="Memory follow-up")

        path = golden.write_golden_snapshot(
            scenario,
            [_turn(0), _turn(1, duration_ms=999)],
            engine_git_sha="deadbee1",
            engine_models={"narrator_model": "gpt-5.4-mini", "director_model": "gpt-5.4-mini"},
        )

        assert path == tmp_path / "memory_follow_up_marcus.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload == {
            "engine_git_sha": "deadbee1",
            "engine_models": {
                "director_model": "gpt-5.4-mini",
                "narrator_model": "gpt-5.4-mini",
            },
            "scenario_id": "memory_follow_up_marcus",
            "scenario_label": "Memory follow-up",
            "schema_version": 1,
            "turns": [
                {
                    "index": 0,
                    "narration": "Narration 0",
                    "player_action": "look around 0",
                    "turn_outputs": {"intent": "observe", "wait": False},
                },
                {
                    "index": 1,
                    "narration": "Narration 1",
                    "player_action": "look around 1",
                    "turn_outputs": {"intent": "observe", "wait": False},
                },
            ],
        }
        assert "duration_ms" not in path.read_text(encoding="utf-8")

    @allure.story("Golden narration")
    @allure.title("golden_path uses benchmarks/golden/<scenario>.json")
    def test_golden_path_layout(self, tmp_path, monkeypatch):
        monkeypatch.setattr(golden, "golden_dir", lambda: tmp_path)

        assert golden.golden_path("world_gen_vividness_florence") == tmp_path / "world_gen_vividness_florence.json"
