"""Offline consumer-seam checks for the matched NPC dialogue pilot."""

from __future__ import annotations

import asyncio
import io
import json
from functools import partial

import allure

from experiments.jev_dialogue_reactions import jev_eval, providers
from experiments.jev_dialogue_reactions.case_data import jev_state, load_cases
from llm.message import LLMResponse


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _fake_urlopen(captured, req, timeout):
    captured.append(json.loads(req.data))
    payload = {
        "answers": {
            "understanding": {"type": "choice", "choice": "partial", "probabilities": {"partial": 1}},
            "expression": {"type": "choice", "choice": "wary", "probabilities": {"wary": 1}},
        },
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }
    return _FakeResponse(json.dumps(payload).encode())


class _FakeClient:
    def __init__(self, captured, **kwargs):
        self.model = "fake"
        self._captured = captured

    async def send_message(self, **kwargs):
        self._captured.append(kwargs)
        return LLMResponse(
            body='{"narration":"I remember the slab you showed me.","mood":null,"status":null,"revealed_names":[]}',
            model="fake",
            usage={"prompt_tokens": 50, "completion_tokens": 10},
        )


@allure.epic("NPC Interaction")
@allure.feature("Jev dialogue pilot")
class TestJevDialoguePilot:
    @allure.story("Fixed cases")
    @allure.title("Pilot contains unknown, learned, role, modern, and Russian controls")
    def test_case_coverage(self):
        cases = load_cases()
        names = [case.name for case in cases]

        assert len(names) == len(set(names)) == 8
        assert any(case.expected_understanding == ["known"] for case in cases)
        assert sum(case.language == "Russian" for case in cases) == 2
        assert sum(case.prior_memory is not None for case in cases) == 2

    @allure.story("Jev seam")
    @allure.title("Jev sees NPC-held claim and returns both typed judgments")
    def test_jev_receives_held_memory_and_two_questions(self, monkeypatch):
        captured = []
        monkeypatch.setattr(jev_eval.request, "urlopen", partial(_fake_urlopen, captured))
        case = next(case for case in load_cases() if case.name == "guard_after_explanation_en")

        result = jev_eval.call_jev(case, "dummy")

        assert captured[0]["model"] == "jev-1.13.0"
        assert case.prior_memory in captured[0]["state"]["held_memory"]
        assert set(captured[0]["questions"]) == {"understanding", "expression"}
        assert "rubric" not in jev_state(case)
        assert result["answers"]["expression"]["choice"] == "wary"

    @allure.story("Actor seam")
    @allure.title("Previously taught fact reaches actual Actor system prompt")
    def test_actor_receives_held_memory(self, monkeypatch):
        captured = []
        monkeypatch.setattr(providers, "OpenAIClient", partial(_FakeClient, captured))
        case = next(case for case in load_cases() if case.name == "guard_after_explanation_en")

        result = asyncio.run(providers.call_actor(case, "baseline", "dummy"))

        assert "traveler claimed" in captured[0]["system_prompt"]
        assert case.player_action in captured[0]["messages"][-1].body
        assert "remember the slab" in result["text"]

    @allure.story("Actor arms")
    @allure.title("Only Jev-guided arm carries the decision cue")
    def test_three_arms_share_player_facts(self):
        case = next(case for case in load_cases() if case.name == "guard_unknown_word_ru")
        jev = {
            "answers": {
                "understanding": {"choice": "unknown"},
                "expression": {"choice": "curious"},
            }
        }
        baseline = providers.actor_input(case, "baseline")
        reminder = providers.actor_input(case, "reminder")
        guided = providers.actor_input(case, "jev", jev)

        assert baseline in reminder
        assert reminder in guided
        assert "understanding=unknown" in guided
        assert "understanding=unknown" not in reminder
