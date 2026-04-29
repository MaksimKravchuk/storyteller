"""Tests for the player web UI (FastAPI JSON API).

Uses ``app.dependency_overrides`` to inject mocks for the config, repository,
player-id cookie, and service layer. The goal is to verify the HTTP contract
and route wiring — engine behavior is covered by existing engine tests.
"""

from __future__ import annotations

from typing import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from fastapi.testclient import TestClient

from interfaces.web import service
from interfaces.web.app import app
from interfaces.web.deps import get_cfg, get_player_id, get_repo
from interfaces.web.character_schemas import CharacterInfo
from interfaces.web.schemas import (
    ActionResponse,
    GameSnapshot,
    TurnEntry,
)
from interfaces.web.transcript import (
    build_transcript,
    render_narrator_html,
    render_player_html,
)

_HTTP_OK = 200
_HTTP_CREATED = 201
_HTTP_NOT_FOUND = 404
_HTTP_UNPROCESSABLE = 422

_FIXED_PLAYER_ID = "11111111-1111-1111-1111-111111111111"
_ANOTHER_PLAYER_ID = "22222222-2222-2222-2222-222222222222"

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Return a repository mock — never hit by FastAPI but required for dep override."""
    return AsyncMock()


@pytest.fixture
def mock_cfg() -> MagicMock:
    return MagicMock(name="Config")


@pytest.fixture
def client(mock_repo, mock_cfg) -> Iterator[TestClient]:
    """FastAPI TestClient with deps overridden. Resets overrides on teardown."""
    app.dependency_overrides[get_cfg] = lambda: mock_cfg
    app.dependency_overrides[get_repo] = lambda: mock_repo
    app.dependency_overrides[get_player_id] = lambda: _FIXED_PLAYER_ID
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _empty_character() -> CharacterInfo:
    return CharacterInfo(
        name="Player",
        appearance="",
        physical_status="healthy",
        inventory=[],
        known_npcs=[],
        recent_events=[],
        learned_facts=[],
    )


def _sample_snapshot(game_id: str = "game-abc", turn_count: int = 0) -> GameSnapshot:
    narrator_text = "The forum stretches before you."
    return GameSnapshot(
        game_id=game_id,
        setting="Rome, 1st century AD",
        transcript=[
            TurnEntry(
                role="narrator",
                text=narrator_text,
                html=render_narrator_html(narrator_text),
            ),
        ],
        turn_count=turn_count,
        character=_empty_character(),
    )


# ---------------------------------------------------------------------------
# build_transcript helper
# ---------------------------------------------------------------------------


@allure.story("Transcript building")
@allure.title("build_transcript emits a player+narrator pair for each conversation_log entry")
def test_build_transcript_pairs_entries() -> None:
    log = [
        {"player_action": "look around", "response": "You see a fountain.", "turn": 1},
        {"player_action": "drink", "response": "The water is cool.", "turn": 2},
    ]
    transcript = build_transcript(log)
    assert [entry.role for entry in transcript] == ["player", "narrator", "player", "narrator"]
    assert transcript[0].text == "look around"
    assert transcript[1].text == "You see a fountain."
    assert transcript[3].text == "The water is cool."


@allure.story("Transcript building")
@allure.title("build_transcript returns an empty list for an empty conversation log")
def test_build_transcript_empty() -> None:
    assert build_transcript([]) == []


@allure.story("Transcript building")
@allure.title("build_transcript skips entries that are missing player_action or response")
def test_build_transcript_skips_missing_fields() -> None:
    log = [
        {"player_action": "look", "response": ""},  # narrator blank → only player line
        {"response": "Silence falls."},  # no player action → only narrator line
    ]
    transcript = build_transcript(log)
    assert [entry.role for entry in transcript] == ["player", "narrator"]
    assert transcript[0].text == "look"
    assert transcript[1].text == "Silence falls."


@allure.story("Transcript building")
@allure.title("build_transcript renders narrator markdown to HTML and HTML-escapes player input")
def test_build_transcript_renders_html_fields() -> None:
    log = [
        {
            "player_action": "look at <Pieter>",
            "response": "**Pieter** stands by the *lantern*.",
        },
    ]
    transcript = build_transcript(log)

    player_entry, narrator_entry = transcript
    # Player text is HTML-escaped (no markdown processing).
    assert player_entry.html == "look at &lt;Pieter&gt;"
    # Narrator markdown is wrapped in <p> with <strong>/<em>.
    assert narrator_entry.html == "<p><strong>Pieter</strong> stands by the <em>lantern</em>.</p>"


@allure.story("Transcript building")
@allure.title("build_transcript rewraps narrator history with inline entity spans from the persisted snapshot")
def test_build_transcript_rewraps_history_entities() -> None:
    log = [
        {
            "player_action": "look",
            "response": "An armed man blocks the door.",
            "visible_entities": [{"kind": "npc", "id": "npc-1", "names": ["an armed man"]}],
        },
    ]
    transcript = build_transcript(log, language="English")
    narrator_entry = transcript[1]
    assert 'data-id="npc-1"' in narrator_entry.html
    assert ">An armed man</span>" in narrator_entry.html


@allure.story("Transcript building")
@allure.title("build_transcript tolerates legacy entries without a visible_entities key")
def test_build_transcript_tolerates_legacy_entries() -> None:
    log = [{"player_action": "look", "response": "A quiet room."}]
    transcript = build_transcript(log, language="English")
    assert transcript[1].html == "<p>A quiet room.</p>"


@allure.story("Transcript building")
@allure.title("build_transcript tolerates every shape of malformed visible_entities payload")
@pytest.mark.parametrize(
    "bad_entities",
    [
        None,
        "not a list",
        {"kind": "npc"},
        [{"kind": "npc", "id": "", "names": ["x"]}],  # validator rejects empty id
        [{"kind": "npc", "id": "n1", "names": []}],  # validator rejects empty names
        [{"kind": "poi"}],  # missing required fields
        ["string inside list"],
        [42],
    ],
)
def test_build_transcript_skips_malformed_visible_entities(bad_entities) -> None:
    log = [
        {
            "player_action": "look",
            "response": "A quiet room.",
            "visible_entities": bad_entities,
        },
    ]
    transcript = build_transcript(log, language="English")
    assert transcript[1].html == "<p>A quiet room.</p>"


@allure.story("Transcript building")
@allure.title("build_transcript rewraps multiple narrator entries in one pass sharing the lemma cache")
def test_build_transcript_rewraps_multiple_entries() -> None:
    entities = [{"kind": "npc", "id": "npc-1", "names": ["страж"]}]
    log = [
        # Inflected forms (genitive, instrumental) both lemmatize to "страж"
        # so the entity wrap hits on both historical entries.
        {"player_action": "осмотреть", "response": "Стража не видно.", "visible_entities": entities},
        {"player_action": "ждать", "response": "Ты говоришь со стражем.", "visible_entities": entities},
    ]
    transcript = build_transcript(log, language="Russian")
    narrator_entries = [entry for entry in transcript if entry.role == "narrator"]
    assert len(narrator_entries) == 2
    assert all('data-id="npc-1"' in entry.html for entry in narrator_entries)


@allure.story("Transcript building")
@allure.title("render_player_html escapes ampersands and angle brackets without applying markdown")
def test_render_player_html_escapes_special_chars() -> None:
    raw = "look at <thing> & say **hi**"
    rendered = render_player_html(raw)
    assert rendered == "look at &lt;thing&gt; &amp; say **hi**"


# ---------------------------------------------------------------------------
# GET / — static index
# ---------------------------------------------------------------------------


@allure.story("Static shell")
@allure.title("GET / serves the index.html page containing the app title")
def test_get_index_serves_html(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == _HTTP_OK
    assert "text/html" in response.headers["content-type"]
    assert "Storyteller" in response.text


@allure.story("Static shell")
@allure.title("GET /healthz returns 200 with a status:ok body and does not touch the repo")
def test_healthz_returns_ok(client: TestClient, mock_repo) -> None:
    response = client.get("/healthz")
    assert response.status_code == _HTTP_OK
    assert response.json() == {"status": "ok"}
    # Liveness probe must not consult the DB.
    mock_repo.sessions.get_latest_web.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/games/current
# ---------------------------------------------------------------------------


@allure.story("Current game lookup")
@allure.title("GET /api/games/current returns 404 when the service has no game for the player")
def test_current_game_returns_404_when_absent(client: TestClient) -> None:
    with patch.object(service, "get_current_snapshot", new=AsyncMock(return_value=None)):
        response = client.get("/api/games/current")
    assert response.status_code == _HTTP_NOT_FOUND
    assert response.json()["detail"] == "No active game"


@allure.story("Current game lookup")
@allure.title("GET /api/games/current returns 200 with the snapshot when a game exists")
def test_current_game_returns_snapshot(client: TestClient) -> None:
    snapshot = _sample_snapshot()
    with patch.object(service, "get_current_snapshot", new=AsyncMock(return_value=snapshot)):
        response = client.get("/api/games/current")
    assert response.status_code == _HTTP_OK
    body = response.json()
    assert body["game_id"] == snapshot.game_id
    assert body["setting"] == snapshot.setting
    first_entry = body["transcript"][0]
    assert first_entry["role"] == "narrator"
    assert first_entry["text"] == "The forum stretches before you."
    assert first_entry["html"] == "<p>The forum stretches before you.</p>"


# ---------------------------------------------------------------------------
# POST /api/games
# ---------------------------------------------------------------------------


@allure.story("Start game")
@allure.title("POST /api/games returns 201 with the opening snapshot on success")
def test_start_game_happy_path(client: TestClient) -> None:
    snapshot = _sample_snapshot()
    start_mock = AsyncMock(return_value=snapshot)
    with patch.object(service, "start_game_for_player", new=start_mock):
        response = client.post("/api/games", json={"setting": "Rome", "language": "Russian"})
    assert response.status_code == _HTTP_CREATED
    assert response.json()["game_id"] == snapshot.game_id
    start_mock.assert_awaited_once()
    # The service received the player id from the overridden dep.
    await_args = start_mock.await_args
    assert await_args is not None
    assert _FIXED_PLAYER_ID in await_args.args
    # The chosen language flowed through to the service call.
    assert "Russian" in await_args.args


@allure.story("Start game")
@allure.title("POST /api/games defaults the language to English when the body omits it")
def test_start_game_defaults_language_to_english(client: TestClient) -> None:
    snapshot = _sample_snapshot()
    start_mock = AsyncMock(return_value=snapshot)
    with patch.object(service, "start_game_for_player", new=start_mock):
        response = client.post("/api/games", json={"setting": "Rome"})
    assert response.status_code == _HTTP_CREATED
    await_args = start_mock.await_args
    assert await_args is not None
    assert "English" in await_args.args


@allure.story("Start game")
@allure.title("POST /api/games rejects an empty setting with HTTP 422")
def test_start_game_rejects_empty_setting(client: TestClient) -> None:
    response = client.post("/api/games", json={"setting": ""})
    assert response.status_code == _HTTP_UNPROCESSABLE


@allure.story("Start game")
@allure.title("POST /api/games rejects a setting longer than 500 characters")
def test_start_game_rejects_oversize_setting(client: TestClient) -> None:
    response = client.post("/api/games", json={"setting": "x" * 501})
    assert response.status_code == _HTTP_UNPROCESSABLE


# ---------------------------------------------------------------------------
# POST /api/games/{game_id}/actions
# ---------------------------------------------------------------------------


@allure.story("Submit action")
@allure.title("POST /api/games/{id}/actions returns narration, narration_html, and turn_count on success")
def test_post_action_happy_path(client: TestClient) -> None:
    action_response = ActionResponse(
        narration="**Pieter** waves.",
        narration_html=render_narrator_html("**Pieter** waves."),
        turn_count=3,
        character=_empty_character(),
    )
    process_mock = AsyncMock(return_value=action_response)
    with patch.object(service, "process_turn_for_player", new=process_mock):
        response = client.post("/api/games/game-abc/actions", json={"action": "look"})
    assert response.status_code == _HTTP_OK
    body = response.json()
    assert body["narration"] == "**Pieter** waves."
    assert body["narration_html"] == "<p><strong>Pieter</strong> waves.</p>"
    assert body["turn_count"] == 3


@allure.story("Submit action")
@allure.title("POST /api/games/{id}/actions returns 404 when no game exists for the player")
def test_post_action_returns_404_when_no_game(client: TestClient) -> None:
    with patch.object(
        service,
        "process_turn_for_player",
        new=AsyncMock(side_effect=service.GameNotFoundError(_FIXED_PLAYER_ID)),
    ):
        response = client.post("/api/games/game-abc/actions", json={"action": "look"})
    assert response.status_code == _HTTP_NOT_FOUND
    assert response.json()["detail"] == "No active game"


@allure.story("Submit action")
@allure.title("POST /api/games/{id}/actions returns 404 when the game_id does not belong to the player")
def test_post_action_hides_ownership_violations(client: TestClient) -> None:
    with patch.object(
        service,
        "process_turn_for_player",
        new=AsyncMock(side_effect=service.GameOwnershipError(_FIXED_PLAYER_ID)),
    ):
        response = client.post("/api/games/other-game/actions", json={"action": "look"})
    assert response.status_code == _HTTP_NOT_FOUND
    assert response.json()["detail"] == "Game not found"


@allure.story("Submit action")
@allure.title("POST /api/games/{id}/actions rejects an empty action body with HTTP 422")
def test_post_action_rejects_empty_action(client: TestClient) -> None:
    response = client.post("/api/games/game-abc/actions", json={"action": ""})
    assert response.status_code == _HTTP_UNPROCESSABLE


# ---------------------------------------------------------------------------
# Cookie bootstrap — uses a client WITHOUT the player_id override
# ---------------------------------------------------------------------------


@pytest.fixture
def cookieless_client(mock_repo, mock_cfg) -> Iterator[TestClient]:
    """A TestClient with only the repo/cfg deps overridden (no player_id stub).

    Used by cookie-bootstrap tests so the real ``player_id_middleware`` runs.
    """
    app.dependency_overrides[get_cfg] = lambda: mock_cfg
    app.dependency_overrides[get_repo] = lambda: mock_repo
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@allure.story("Cookie bootstrap")
@allure.title("First request without a cookie mints a web_player_id cookie that persists across requests")
def test_cookie_bootstrap_and_reuse(cookieless_client: TestClient) -> None:
    with patch.object(service, "get_current_snapshot", new=AsyncMock(return_value=None)):
        first = cookieless_client.get("/api/games/current")
        second = cookieless_client.get("/api/games/current")
    assert first.status_code == _HTTP_NOT_FOUND
    assert "web_player_id" in first.cookies
    minted_id = first.cookies["web_player_id"]
    assert cookieless_client.cookies.get("web_player_id") == minted_id
    assert second.status_code == _HTTP_NOT_FOUND


@allure.story("Cookie bootstrap")
@allure.title("Two TestClients receive different web_player_id cookies so player state is isolated")
def test_distinct_clients_get_distinct_player_ids(mock_repo, mock_cfg) -> None:
    """Two clients reach the cookie middleware independently and get distinct ids."""
    app.dependency_overrides[get_cfg] = lambda: mock_cfg
    app.dependency_overrides[get_repo] = lambda: mock_repo
    try:
        _hit_two_clients_once()
    finally:
        app.dependency_overrides.clear()


def _hit_two_clients_once() -> None:
    """Send one request through each of two fresh TestClients and assert distinct cookies."""
    with patch.object(service, "get_current_snapshot", new=AsyncMock(return_value=None)):
        alice = TestClient(app)
        bob = TestClient(app)
        alice.get("/api/games/current")
        bob.get("/api/games/current")
    assert alice.cookies["web_player_id"] != bob.cookies["web_player_id"]


# ---------------------------------------------------------------------------
# Service layer: game-ownership check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@allure.story("Ownership enforcement")
@allure.title("process_turn_for_player raises GameOwnershipError when game_id does not match the loaded game")
async def test_process_turn_enforces_ownership() -> None:
    repo = AsyncMock()
    repo.sessions = MagicMock()
    repo.sessions.get_latest_web = AsyncMock(return_value={"id": "sess-1", "language": "English"})

    loaded_state = MagicMock()
    loaded_state.uuid = "real-game-id"
    repo.load_game_state.return_value = (loaded_state, MagicMock(), [])

    with pytest.raises(service.GameOwnershipError):
        await service.process_turn_for_player(
            repo=repo,
            cfg=MagicMock(),
            player_id=_ANOTHER_PLAYER_ID,
            game_id="wrong-game-id",
            action="look",
        )


@pytest.mark.asyncio
@allure.story("Ownership enforcement")
@allure.title("process_turn_for_player raises GameNotFoundError when the player has no saved game")
async def test_process_turn_raises_when_no_game() -> None:
    repo = AsyncMock()
    repo.sessions = MagicMock()
    repo.sessions.get_latest_web = AsyncMock(return_value={"id": "sess-1", "language": "English"})
    repo.load_game_state.return_value = None

    with pytest.raises(service.GameNotFoundError):
        await service.process_turn_for_player(
            repo=repo,
            cfg=MagicMock(),
            player_id=_FIXED_PLAYER_ID,
            game_id="game-abc",
            action="look",
        )


@pytest.mark.asyncio
@allure.story("Ownership enforcement")
@allure.title("_act_and_persist raises RuntimeError when the engine has no game_state after the action")
async def test_act_and_persist_raises_when_engine_has_no_game_state() -> None:
    """Guards the invariant strengthened in the KER-30 refactor: the old
    ``turn_number or 0`` fallback silently masked a broken engine that had no
    ``game_state``. The raise now surfaces that as a 500 instead of assembling
    an ActionResponse with turn_count=0.
    """
    repo = AsyncMock()
    engine = MagicMock()
    engine.game_state = None
    engine.process_action = AsyncMock(return_value="prose")

    with pytest.raises(RuntimeError, match="engine.game_state is None"):
        await service._act_and_persist(repo, "sess-1", engine, "look", "English")


@pytest.mark.asyncio
@allure.story("Ownership enforcement")
@allure.title("process_turn_for_player raises GameNotFoundError when the player has no session row at all")
async def test_process_turn_raises_when_no_session() -> None:
    repo = AsyncMock()
    repo.sessions = MagicMock()
    repo.sessions.get_latest_web = AsyncMock(return_value=None)

    with pytest.raises(service.GameNotFoundError):
        await service.process_turn_for_player(
            repo=repo,
            cfg=MagicMock(),
            player_id=_FIXED_PLAYER_ID,
            game_id="game-abc",
            action="look",
        )


@pytest.mark.asyncio
@allure.story("Start game")
@allure.title("start_game_for_player creates a new session row on every call, preserving prior sessions")
async def test_start_game_creates_fresh_session_each_call() -> None:
    repo = AsyncMock()
    repo.sessions = MagicMock()
    repo.sessions.create_web = AsyncMock(
        side_effect=[
            {"id": "sess-1", "language": "English"},
            {"id": "sess-2", "language": "English"},
        ],
    )
    repo.sessions.update = AsyncMock()
    repo.save_game_state.return_value = None

    engine = MagicMock()
    engine.start_game = AsyncMock()
    engine.knowledge_graph = MagicMock()
    engine.event_manager = MagicMock(all_events=[])
    engine.game_state = MagicMock()
    engine.game_state.uuid = "game-1"
    engine.game_state.setting.name = "Rome"
    engine.game_state.conversation_log = []
    engine.game_state.turn_count = 0
    engine.game_state.player = MagicMock(
        name="Player",
        appearance="",
        physical_status="healthy",
        inventory=[],
        known_npcs=set(),
        player_event_log=[],
        learned_facts=set(),
    )
    # MagicMock coerces the kwarg ``name`` to the mock's own name; re-set it explicitly.
    engine.game_state.player.name = "Player"
    engine.game_state.npcs = {}

    with (
        patch("interfaces.web.service.create_engine", return_value=engine),
        patch("engine.model_overrides.load_role_overrides", new=AsyncMock(return_value={})),
    ):
        await service.start_game_for_player(
            repo=repo,
            cfg=MagicMock(),
            player_id=_FIXED_PLAYER_ID,
            setting="Rome",
            language="English",
        )
        await service.start_game_for_player(
            repo=repo,
            cfg=MagicMock(),
            player_id=_FIXED_PLAYER_ID,
            setting="Rome",
            language="English",
        )

    create_calls = repo.sessions.create_web.await_args_list
    assert len(create_calls) == 2
    assert all(call.args == (_FIXED_PLAYER_ID,) for call in create_calls)
    save_calls = repo.save_game_state.await_args_list
    assert {call.args[0] for call in save_calls} == {"sess-1", "sess-2"}
