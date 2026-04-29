"""Unit tests for :mod:`benchmarks.harness.transcript` — narrator capture."""

from __future__ import annotations

import allure
import pytest

from benchmarks.harness.transcript import NarratorCapture
from cast.schemas.turn_outputs import DialogueEntry, TurnOutputs


class _StubNarrator:
    """Minimal stand-in for the engine's Narrator — records execute calls."""

    def __init__(self) -> None:
        self.calls: list = []

    async def execute(self, input_data, context=None):
        self.calls.append(input_data)
        return "narration-{0}".format(len(self.calls))


class _StubDirector:
    def __init__(self, narrator: _StubNarrator) -> None:
        self._narrator = narrator


class _StubEngine:
    """Stand-in for ``GameEngine`` exposing the private ``_director`` attribute."""

    def __init__(self, director) -> None:
        self._director = director


def _outputs() -> TurnOutputs:
    return TurnOutputs(dialogue=[DialogueEntry(npc_name="Marcus", response="Hi")])


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestNarratorCaptureAttach:
    @allure.story("Narrator capture")
    @allure.title("attach raises RuntimeError when the engine has no restored director to wrap")
    def test_attach_without_director_raises(self):
        engine = _StubEngine(director=None)
        capture = NarratorCapture()

        with pytest.raises(RuntimeError, match="running engine"):
            capture.attach(engine)

    @allure.story("Narrator capture")
    @allure.title("attach swaps the narrator's execute with a wrapper that records TurnOutputs payloads")
    @pytest.mark.asyncio
    async def test_attach_wraps_execute_and_records_payloads(self):
        narrator = _StubNarrator()
        engine = _StubEngine(_StubDirector(narrator))
        capture = NarratorCapture()
        capture.attach(engine)

        payload = _outputs()
        result = await narrator.execute(payload)

        assert result == "narration-1"
        assert capture.outputs == [payload]

    @allure.story("Narrator capture")
    @allure.title("attach ignores non-TurnOutputs inputs but still forwards them to the real narrator")
    @pytest.mark.asyncio
    async def test_non_turn_outputs_input_forwarded_but_not_buffered(self):
        narrator = _StubNarrator()
        engine = _StubEngine(_StubDirector(narrator))
        capture = NarratorCapture()
        capture.attach(engine)

        result = await narrator.execute("a string that is not TurnOutputs")

        assert result == "narration-1"
        assert capture.outputs == []


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestNarratorCapturePopNext:
    @allure.story("Narrator capture")
    @allure.title("pop_next returns buffered payloads in FIFO order")
    @pytest.mark.asyncio
    async def test_pop_next_fifo(self):
        narrator = _StubNarrator()
        engine = _StubEngine(_StubDirector(narrator))
        capture = NarratorCapture()
        capture.attach(engine)
        first_payload = _outputs()
        second_payload = _outputs()
        await narrator.execute(first_payload)
        await narrator.execute(second_payload)

        assert capture.pop_next() is first_payload
        assert capture.pop_next() is second_payload

    @allure.story("Narrator capture")
    @allure.title("pop_next raises IndexError when the buffer is empty so short-circuit turns fail loudly")
    def test_pop_next_empty_raises(self):
        capture = NarratorCapture()

        with pytest.raises(IndexError, match="empty"):
            capture.pop_next()
