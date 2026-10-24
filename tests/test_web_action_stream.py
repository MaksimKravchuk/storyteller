"""Tests for the streamed player-turn route (``POST /api/games/{id}/actions/stream``)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from fastapi.testclient import TestClient

from interfaces.web import action_stream, deps, service
from interfaces.web.app import app
from interfaces.web.schemas import ActionResponse
from llm import turn_stream
from tests.test_web_api import _empty_character, _sample_world

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]

_URL = "/api/games/game-1/actions/stream"
_RESPONSE = ActionResponse(
    narration="Rain falls.",
    narration_html="<p>Rain falls.</p>",
    action_html="<p>wait</p>",
    turn_count=2,
    character=_empty_character(),
    world=_sample_world(),
)


def _events(body: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into (event, data) pairs."""
    parsed = []
    for frame in body.strip().split("\n\n"):
        name_line, data_line = frame.split("\n")
        parsed.append((name_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))))
    return parsed


async def _fake_turn(*args: object) -> ActionResponse:
    await turn_stream.emit_stage("acting")
    handler = turn_stream.delta_handler()
    assert handler is not None
    await handler("Rain ")
    await handler("falls.")
    return _RESPONSE


async def _slow_turn(release: asyncio.Event, finished: list[bool]) -> ActionResponse:
    await turn_stream.emit_stage("acting")
    await release.wait()
    finished.append(True)
    return _RESPONSE


@pytest.fixture
def client():
    cfg = MagicMock(name="Config")
    repo = AsyncMock()
    app.dependency_overrides[deps.get_cfg] = lambda: cfg
    app.dependency_overrides[deps.get_repo] = lambda: repo
    app.dependency_overrides[deps.get_player_id] = lambda: "11111111-1111-1111-1111-111111111111"
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@allure.story("Streamed turn")
@allure.title("Streamed turn emits stage and delta events, then done with the full ActionResponse")
def test_stream_happy_path(client) -> None:
    with patch.object(service, "process_turn_for_player", new=AsyncMock(side_effect=_fake_turn)):
        response = client.post(_URL, json={"action": "wait"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert _events(response.text) == [
        ("stage", {"stage": "acting"}),
        ("delta", {"text": "Rain "}),
        ("delta", {"text": "falls."}),
        ("done", _RESPONSE.model_dump(mode="json")),
    ]


@allure.story("Streamed turn")
@allure.title("A service error becomes one error event carrying the status the plain route would return")
def test_stream_maps_service_error(client) -> None:
    failing = AsyncMock(side_effect=service.GameNotFoundError("p"))
    with patch.object(service, "process_turn_for_player", new=failing):
        response = client.post(_URL, json={"action": "wait"})

    assert _events(response.text) == [("error", {"status": 404, "detail": "No active game"})]


@allure.story("Streamed turn")
@allure.title("An unexpected failure becomes a generic 500 error event without leaking internals")
def test_stream_maps_unexpected_error(client) -> None:
    failing = AsyncMock(side_effect=RuntimeError("db exploded"))
    with patch.object(service, "process_turn_for_player", new=failing):
        response = client.post(_URL, json={"action": "wait"})

    events = _events(response.text)
    assert len(events) == 1
    name, payload = events[0]
    assert name == "error"
    assert payload["status"] == 500
    assert "exploded" not in payload["detail"]


@allure.story("Streamed turn")
@allure.title("Closing the stream early still lets the turn finish so a paid turn is persisted")
@pytest.mark.asyncio
async def test_stream_close_waits_for_turn() -> None:
    release = asyncio.Event()
    finished: list[bool] = []
    frames = action_stream.stream_turn(lambda: _slow_turn(release, finished))
    first = await frames.__anext__()
    assert first.startswith("event: stage")
    asyncio.get_running_loop().call_later(0.01, release.set)
    await frames.aclose()
    assert finished == [True]
