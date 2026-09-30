"""Offline checks for the controlled Jev versus Actor reaction pilot."""

from __future__ import annotations

import asyncio
import io
import json
import math
from functools import partial

import allure

from experiments.jev_npc_reactions import actor_eval, jev_eval
from experiments.jev_npc_reactions.case_data import jev_state, load_cases
from experiments.jev_npc_reactions.run import main, run
from llm.message import LLMResponse


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _fake_urlopen(captured, request, timeout):
    captured.append(json.loads(request.data))
    response = {
        "answers": {"next_action": {"type": "choice", "choice": "restrain", "probabilities": {"restrain": 1}}},
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 100, "output_tokens": 1},
    }
    return _FakeResponse(json.dumps(response).encode())


class _FakeClient:
    def __init__(self, captured, **kwargs):
        self.model = "fake"
        self._captured = captured

    async def send_message(self, **kwargs):
        self._captured.append(kwargs)
        return LLMResponse(body='{"action":"retreats","type":"MOVE","target":null}', model="fake")


@allure.epic("NPC Interaction")
@allure.feature("Jev reaction pilot")
class TestJevReactionPilot:
    @allure.story("Controlled inputs")
    @allure.title("Angry guard has the same dice chance across attack and surrender")
    def test_dice_baseline_cannot_distinguish_surrender(self):
        rows = {row["case"]: row for row in asyncio.run(run(live=False))}

        assert math.isclose(rows["guard_active_assault"]["dice_attack_probability"], 0.65)
        assert math.isclose(rows["guard_surrender"]["dice_attack_probability"], 0.65)
        assert rows["guard_active_assault"]["state"]["scene"] != rows["guard_surrender"]["state"]["scene"]

    @allure.story("Controlled inputs")
    @allure.title("Merchant role facts reach Jev's input state")
    def test_jev_receives_character_equipment(self):
        merchant = next(case for case in load_cases() if case.name == "merchant_threat")
        state = jev_state(merchant)

        assert state["npc"]["role"] == "merchant"
        assert "market trader" in state["npc"]["biography"]
        assert "dagger" in state["last_player_action"]

    @allure.story("Provider seam")
    @allure.title("Jev request uses pinned choice model and returns distribution")
    def test_jev_request_shape(self, monkeypatch):
        captured = []

        monkeypatch.setattr(jev_eval.request, "urlopen", partial(_fake_urlopen, captured))
        case = next(case for case in load_cases() if case.name == "guard_surrender")
        answer = jev_eval.call_jev(case, "dummy")

        assert captured[0]["model"] == "jev-1.13.0"
        assert captured[0]["questions"]["next_action"]["type"] == "choice"
        assert captured[0]["state"]["last_player_action"] == case.player_action
        assert answer["answer"]["choice"] == "restrain"

    @allure.story("Actor seam")
    @allure.title("Existing Actor receives merchant facts through its action prompt")
    def test_actor_receives_matching_character_context(self, monkeypatch):
        captured = []

        monkeypatch.setattr(actor_eval, "OpenAIClient", partial(_FakeClient, captured))
        case = next(case for case in load_cases() if case.name == "merchant_threat")
        answer = asyncio.run(actor_eval.call_actor(case, "dummy"))

        assert "market trader" in captured[0]["system_prompt"]
        assert "purse" in captured[0]["system_prompt"]
        assert case.player_action in captured[0]["messages"][-1].body
        assert "retreats" in answer["text"]

    @allure.story("Runner output")
    @allure.title("Default output lands in the platform temp directory")
    def test_default_output_uses_platform_temp_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
        monkeypatch.setattr("sys.argv", ["run.py"])

        main()

        rows = json.loads((tmp_path / "storyteller_jev_results.json").read_text())
        assert len(rows) == len(load_cases())
