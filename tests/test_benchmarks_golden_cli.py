"""Unit tests for the ``benchmarks golden-update`` subcommand."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import allure
import pytest

from benchmarks.cli import _golden_update
from benchmarks.cli._args import parse_args
from benchmarks.cli._async_commands import ASYNC_COMMANDS
from benchmarks.harness import golden


class _TurnOutputs:
    """Small stand-in for TurnOutputs with the model_dump contract."""

    def model_dump(self, *, mode: str) -> dict:
        assert mode == "json"
        return {"wait": False, "intent": "inspect"}


def _turn() -> SimpleNamespace:
    return SimpleNamespace(
        index=0,
        player_action="Inspect the shrine",
        narration="Dust curls around the shrine.",
        turn_outputs=_TurnOutputs(),
        duration_ms=321,
    )


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        director_model="gpt-5.4-mini-2026-04-01",
        agent_model="gpt-5.4-mini-2026-04-01",
        narrator_model="gpt-5.4-mini-2026-04-01",
        dramaturge_model="gpt-5.4-mini-2026-04-01",
        dramaturge_enabled=False,
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark CLI")
class TestGoldenUpdateArgs:
    @allure.story("CLI parsing")
    @allure.title("golden-update is discoverable as a scenario-id subcommand")
    def test_golden_update_args(self):
        args = parse_args(["golden-update", "memory_follow_up_marcus"])

        assert args.command == "golden-update"
        assert args.scenario_id == "memory_follow_up_marcus"
        assert "golden-update" in ASYNC_COMMANDS


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark CLI")
class TestGoldenUpdateCommand:
    @allure.story("Golden narration")
    @allure.title("golden-update captures one scenario and writes deterministic JSON")
    @pytest.mark.asyncio
    async def test_writes_golden_snapshot(self, tmp_path, monkeypatch, capsys):
        scenario = SimpleNamespace(id="memory_follow_up_marcus", label="Memory follow-up")
        fake_cfg = _cfg()
        run_script = AsyncMock(return_value=([_turn()], []))
        monkeypatch.setattr(golden, "golden_dir", lambda: tmp_path)
        monkeypatch.setattr(_golden_update, "get_scenario", Mock(return_value=scenario))
        monkeypatch.setattr(_golden_update, "load_config", lambda: fake_cfg)
        monkeypatch.setattr(_golden_update, "current_git_sha", lambda: "deadbee1")
        monkeypatch.setattr(_golden_update, "_run_script", run_script)

        exit_code = await _golden_update.golden_update_command(
            SimpleNamespace(scenario_id="memory_follow_up_marcus"),
        )

        assert exit_code == 0
        run_script.assert_awaited_once_with(scenario, fake_cfg)
        out = capsys.readouterr().out
        assert "Golden updated memory_follow_up_marcus" in out
        payload = json.loads((tmp_path / "memory_follow_up_marcus.json").read_text(encoding="utf-8"))
        assert payload["scenario_id"] == "memory_follow_up_marcus"
        assert payload["engine_git_sha"] == "deadbee1"
        assert payload["engine_models"] == {
            "agent_model": "gpt-5.4-mini-2026-04-01",
            "director_model": "gpt-5.4-mini-2026-04-01",
            "dramaturge_enabled": "false",
            "dramaturge_model": "gpt-5.4-mini-2026-04-01",
            "narrator_model": "gpt-5.4-mini-2026-04-01",
        }
        assert payload["turns"] == [
            {
                "index": 0,
                "narration": "Dust curls around the shrine.",
                "player_action": "Inspect the shrine",
                "turn_outputs": {"intent": "inspect", "wait": False},
            },
        ]

    @allure.story("Golden narration")
    @allure.title("golden-update returns exit code 2 for an unknown scenario id")
    @pytest.mark.asyncio
    async def test_unknown_scenario_exits_2(self, monkeypatch, capsys):
        monkeypatch.setattr(
            _golden_update,
            "get_scenario",
            Mock(side_effect=KeyError("Unknown scenario id 'missing'. Known: memory_follow_up_marcus")),
        )

        exit_code = await _golden_update.golden_update_command(SimpleNamespace(scenario_id="missing"))

        assert exit_code == 2
        err = capsys.readouterr().err
        assert err.startswith("Unknown scenario id")
