"""Tests for the mobile HTTP/SSE API (``interfaces.api``).

The Director (and the rest of the engine cast) is mocked end-to-end via
a fake ``EngineFactory``. The goal is to verify the HTTP contract, the
SSE framing, and the in-memory session store wiring — engine internals
are covered by their own tests.
"""

from __future__ import annotations

import json
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock

import allure
import pytest
from fastapi.testclient import TestClient

from interfaces.api.app import app
from interfaces.api.deps import get_engine_factory, get_session_store
from interfaces.api.sessions import SessionStore

_HTTP_OK = 200
_HTTP_CREATED = 201
_HTTP_NOT_FOUND = 404
_HTTP_UNPROCESSABLE = 422

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Mobile API"),
]


class _FakeEngine:
    """Director-free stand-in for ``GameEngine`` used by the route tests.

    Records every call so tests can assert on what the routes invoked,
    and lets each test script ``start_game`` / ``process_action`` return
    values without booting an LLM client or knowledge graph.
    """

    def __init__(
        self,
        *,
        opening: str = "You stand in a quiet courtyard.",
        narration: str = "You take a step forward.",
        inventory: list[str] | None = None,
        scene_description: str = "A quiet courtyard at dawn.",
    ) -> None:
        self._opening = opening
        self._narration = narration
        self._inventory = list(inventory or [])
        self._scene_description = scene_description
        self.start_calls: list[tuple[str, object]] = []
        self.action_calls: list[str] = []
        self._turn_count = 0
        self._started = False

    async def start_game(self, setting: str, character: object = None) -> str:
        self.start_calls.append((setting, character))
        self._started = True
        return self._opening

    async def process_action(self, action: str) -> str:
        if not self._started:
            raise RuntimeError("Game not started.")
        self.action_calls.append(action)
        self._turn_count += 1
        return self._narration

    def assert_running(self):
        if not self._started:
            raise RuntimeError("Game not started.")
        scene = MagicMock(description=self._scene_description)
        player = MagicMock(inventory=list(self._inventory))
        state = MagicMock(
            current_scene=scene,
            player=player,
            turn_count=self._turn_count,
        )
        return state, MagicMock(), MagicMock()


class _FakeEngineFactory:
    """Pluggable factory that hands out pre-seeded ``_FakeEngine`` instances."""

    def __init__(self, engines: list[_FakeEngine] | None = None) -> None:
        self.engines = list(engines or [])
        self.built: list[str] = []

    def build(self, language: str):
        self.built.append(language)
        if self.engines:
            return self.engines.pop(0)
        return _FakeEngine()


@pytest.fixture
def store() -> SessionStore:
    return SessionStore()


@pytest.fixture
def factory() -> _FakeEngineFactory:
    return _FakeEngineFactory()


@pytest.fixture
def client(store: SessionStore, factory: _FakeEngineFactory) -> Iterator[TestClient]:
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_engine_factory] = lambda: factory
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _parse_sse(raw: str) -> list[dict]:
    """Parse the SSE wire format used by ``stream_narration``."""
    frames: list[dict] = []
    for block in raw.strip().split("\n\n"):
        event = None
        payload = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                payload = line.split(":", 1)[1].strip()
        frames.append({"event": event, "data": json.loads(payload) if payload else None})
    return frames


# ---------------------------------------------------------------------------
# GET /healthz
# ---------------------------------------------------------------------------


@allure.story("Liveness")
@allure.title("GET /healthz returns 200 with status:ok and never touches the engine factory")
def test_healthz_returns_ok(client: TestClient, factory: _FakeEngineFactory) -> None:
    response = client.get("/healthz")
    assert response.status_code == _HTTP_OK
    assert response.json() == {"status": "ok"}
    assert factory.built == []


# ---------------------------------------------------------------------------
# POST /sessions
# ---------------------------------------------------------------------------


@allure.story("Create session")
@allure.title("POST /sessions returns 201 with the opening scene and a fresh session_id")
def test_create_session_returns_opening_scene(
    client: TestClient,
    store: SessionStore,
    factory: _FakeEngineFactory,
) -> None:
    engine = _FakeEngine(opening="The forum stretches before you.")
    factory.engines.append(engine)

    response = client.post("/sessions", json={"setting": "Rome, 1st century AD"})

    assert response.status_code == _HTTP_CREATED
    body = response.json()
    assert body["setting"] == "Rome, 1st century AD"
    assert body["opening_scene"] == "The forum stretches before you."
    assert body["language"] == "English"
    assert body["turn_count"] == 0
    assert body["session_id"]
    # Engine was actually driven by the service layer.
    assert engine.start_calls == [("Rome, 1st century AD", None)]
    # Session is registered with the store.
    assert store.get(body["session_id"]) is not None


@allure.story("Create session")
@allure.title("POST /sessions forwards the language to the engine factory and persists it on the session")
def test_create_session_forwards_language(
    client: TestClient,
    factory: _FakeEngineFactory,
) -> None:
    response = client.post("/sessions", json={"setting": "Kyoto, 1605", "language": "Japanese"})
    assert response.status_code == _HTTP_CREATED
    assert response.json()["language"] == "Japanese"
    assert factory.built == ["Japanese"]


@allure.story("Create session")
@allure.title("POST /sessions rejects an empty setting with HTTP 422")
def test_create_session_rejects_empty_setting(client: TestClient) -> None:
    response = client.post("/sessions", json={"setting": ""})
    assert response.status_code == _HTTP_UNPROCESSABLE


@allure.story("Create session")
@allure.title("POST /sessions rejects a setting longer than 500 characters")
def test_create_session_rejects_oversize_setting(client: TestClient) -> None:
    response = client.post("/sessions", json={"setting": "x" * 501})
    assert response.status_code == _HTTP_UNPROCESSABLE


# ---------------------------------------------------------------------------
# POST /sessions/{id}/actions
# ---------------------------------------------------------------------------


@allure.story("Submit action")
@allure.title("POST /sessions/{id}/actions streams chunk events followed by a done event with the new turn_count")
def test_post_action_streams_chunks_then_done(
    client: TestClient,
    factory: _FakeEngineFactory,
) -> None:
    factory.engines.append(_FakeEngine(narration="You draw your sword and step forward."))
    created = client.post("/sessions", json={"setting": "Rome"}).json()

    response = client.post(
        "/sessions/{0}/actions".format(created["session_id"]),
        json={"action": "look around"},
    )
    assert response.status_code == _HTTP_OK
    assert response.headers["content-type"].startswith("text/event-stream")

    frames = _parse_sse(response.text)
    chunk_frames = [frame for frame in frames if frame["event"] == "chunk"]
    done_frames = [frame for frame in frames if frame["event"] == "done"]
    assert chunk_frames, "expected at least one chunk frame"
    assert len(done_frames) == 1
    # Re-assembling chunks must reproduce the narration exactly.
    assembled = "".join(frame["data"]["text"] for frame in chunk_frames)
    assert assembled == "You draw your sword and step forward."
    done_payload = done_frames[0]["data"]
    assert done_payload["narration"] == "You draw your sword and step forward."
    assert done_payload["turn_count"] == 1


@allure.story("Submit action")
@allure.title("POST /sessions/{id}/actions emits an error SSE frame when the session_id is unknown")
def test_post_action_unknown_session_emits_error_frame(client: TestClient) -> None:
    response = client.post(
        "/sessions/no-such-session/actions",
        json={"action": "look"},
    )
    # SSE responses always return 200; failure is surfaced inside the stream.
    assert response.status_code == _HTTP_OK
    frames = _parse_sse(response.text)
    assert [frame["event"] for frame in frames] == ["error"]
    assert frames[0]["data"]["detail"] == "Session not found"


@allure.story("Submit action")
@allure.title("POST /sessions/{id}/actions rejects an empty action body with HTTP 422")
def test_post_action_rejects_empty_action(client: TestClient) -> None:
    response = client.post("/sessions/anything/actions", json={"action": ""})
    assert response.status_code == _HTTP_UNPROCESSABLE


@allure.story("Submit action")
@allure.title("POST /sessions/{id}/actions advances the engine turn_count visible on GET /sessions/{id}")
def test_post_action_increments_turn_count_on_get(
    client: TestClient,
    factory: _FakeEngineFactory,
) -> None:
    factory.engines.append(_FakeEngine())
    session_id = client.post("/sessions", json={"setting": "Rome"}).json()["session_id"]

    client.post("/sessions/{0}/actions".format(session_id), json={"action": "look"})
    client.post("/sessions/{0}/actions".format(session_id), json={"action": "wait"})

    state = client.get("/sessions/{0}".format(session_id)).json()
    assert state["turn_count"] == 2
    roles = [entry["role"] for entry in state["recent_transcript"]]
    # Opening narrator + two player/narrator pairs.
    assert roles == ["narrator", "player", "narrator", "player", "narrator"]


# ---------------------------------------------------------------------------
# GET /sessions/{id}
# ---------------------------------------------------------------------------


@allure.story("Get session")
@allure.title("GET /sessions/{id} returns 200 with scene description, inventory, and the opening transcript")
def test_get_session_returns_state(
    client: TestClient,
    factory: _FakeEngineFactory,
) -> None:
    factory.engines.append(
        _FakeEngine(
            opening="A quiet courtyard.",
            scene_description="A quiet courtyard at dawn.",
            inventory=["coin", "letter"],
        ),
    )
    session_id = client.post("/sessions", json={"setting": "Florence, 1480"}).json()["session_id"]

    response = client.get("/sessions/{0}".format(session_id))
    assert response.status_code == _HTTP_OK
    body = response.json()
    assert body["session_id"] == session_id
    assert body["setting"] == "Florence, 1480"
    assert body["scene_description"] == "A quiet courtyard at dawn."
    assert body["inventory"] == ["coin", "letter"]
    assert body["recent_transcript"] == [{"role": "narrator", "text": "A quiet courtyard."}]


@allure.story("Get session")
@allure.title("GET /sessions/{id} returns 404 when the session_id is unknown")
def test_get_session_returns_404_when_missing(client: TestClient) -> None:
    response = client.get("/sessions/no-such-session")
    assert response.status_code == _HTTP_NOT_FOUND
    assert response.json()["detail"] == "Session not found"


# ---------------------------------------------------------------------------
# GET /sessions
# ---------------------------------------------------------------------------


@allure.story("List sessions")
@allure.title("GET /sessions returns every live session ordered by created_at")
def test_list_sessions_returns_all(
    client: TestClient,
    factory: _FakeEngineFactory,
) -> None:
    factory.engines.extend([_FakeEngine(), _FakeEngine()])
    client.post("/sessions", json={"setting": "Rome"})
    client.post("/sessions", json={"setting": "Kyoto"})

    body = client.get("/sessions").json()
    settings = [entry["setting"] for entry in body["sessions"]]
    assert settings == ["Rome", "Kyoto"]


@allure.story("List sessions")
@allure.title("GET /sessions returns an empty list when no sessions exist")
def test_list_sessions_empty(client: TestClient) -> None:
    body = client.get("/sessions").json()
    assert body == {"sessions": []}


# ---------------------------------------------------------------------------
# Engine failure surface
# ---------------------------------------------------------------------------


@allure.story("Create session")
@allure.title("POST /sessions surfaces engine failures as HTTP 500 rather than partially registering a session")
def test_create_session_engine_failure_does_not_register(
    client: TestClient,
    store: SessionStore,
    factory: _FakeEngineFactory,
) -> None:
    failing_engine = _FakeEngine()
    failing_engine.start_game = AsyncMock(side_effect=RuntimeError("data miner crashed"))  # type: ignore[assignment]
    factory.engines.append(failing_engine)

    with pytest.raises(RuntimeError, match="data miner crashed"):
        client.post("/sessions", json={"setting": "Rome"})

    assert store.list_all() == []
