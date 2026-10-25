"""Consumer-seam tests: the Narrator streams its prose into a bound turn stream."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

import allure
import pytest

from cast.narrator import Narrator
from cast.schemas.turn_outputs import TurnOutputs
from llm import turn_stream
from llm.base_client import BaseLLMClient, OutputFormat
from llm.message import LLMResponse, Message
from models.game_state import GameState
from tests._turn_stream_helpers import RecordingSink

pytestmark = [
    allure.epic("Narrative Delivery"),
    allure.feature("Live turn stream"),
]


class _PlainClient(BaseLLMClient):
    """LLM client without native streaming: inherits the base ``stream_message``."""

    def __init__(self, chunks: list[str]) -> None:
        super().__init__(model="chunked")
        self._chunks = chunks

    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        output_format: OutputFormat | None = None,
    ) -> LLMResponse:
        return LLMResponse(body="".join(self._chunks), model=self.model)


class _ChunkedClient(_PlainClient):
    """LLM client that streams a fixed body in fixed chunks."""

    def __init__(self, chunks: list[str]) -> None:
        super().__init__(chunks)
        self.streamed = False

    async def stream_message(
        self,
        messages: list[Message],
        on_delta: Callable[[str], Awaitable[None]],
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.streamed = True
        # gather starts the recording callbacks in order, so chunk order is kept.
        await asyncio.gather(*(on_delta(chunk) for chunk in self._chunks))
        return LLMResponse(body="".join(self._chunks), model=self.model)


async def _narrate(narrator: Narrator, game_state: GameState, **context: Any) -> str:
    return await narrator.act(
        input_data=TurnOutputs(),
        context={"player_action": "look", "game_state": game_state, **context},
    )


@allure.story("Narrator seam")
@allure.title("Narrator streams its prose into the bound sink and announces the narrating stage")
@pytest.mark.asyncio
async def test_narrator_streams_into_sink(game_state: GameState) -> None:
    client = _ChunkedClient(["Mist ", "rolls in."])
    narrator = Narrator(llm_client=client, language="English")
    sink = RecordingSink()

    with turn_stream.bound(sink):
        narration = await _narrate(narrator, game_state)

    assert client.streamed
    assert narration == "Mist rolls in."
    assert sink.stages == ["narrating"]
    assert sink.deltas == ["Mist ", "rolls in."]


@allure.story("Narrator seam")
@allure.title("Narrator does not stream a passage marked stream_live=False (Dramaturge will review it)")
@pytest.mark.asyncio
async def test_narrator_respects_stream_live_false(game_state: GameState) -> None:
    client = _ChunkedClient(["Mist."])
    sink = RecordingSink()

    with turn_stream.bound(sink):
        await _narrate(Narrator(llm_client=client, language="English"), game_state, stream_live=False)

    assert not client.streamed
    assert sink.deltas == []


@allure.story("Narrator seam")
@allure.title("Narrator uses the plain send path when no sink is bound")
@pytest.mark.asyncio
async def test_narrator_without_sink_does_not_stream(game_state: GameState) -> None:
    client = _ChunkedClient(["Mist."])
    assert await _narrate(Narrator(llm_client=client, language="English"), game_state) == "Mist."
    assert not client.streamed


@allure.story("Base client")
@allure.title("BaseLLMClient.stream_message default delivers the whole body as a single delta")
@pytest.mark.asyncio
async def test_base_client_default_stream_message() -> None:
    sink = RecordingSink()
    response = await _PlainClient(["a", "b"]).stream_message([], on_delta=sink.delta)
    assert response.body == "ab"
    assert sink.deltas == ["ab"]
