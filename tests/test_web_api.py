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
_HTTP_INTERNAL_SERVER_ERROR = 500
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


@pytest.fixture
def non_raising_client(mock_repo, mock_cfg) -> Iterator[TestClient]:
    """TestClient that returns 500 responses instead of re-raising server exceptions."""
    app.dependency_overrides[get_cfg] = lambda: mock_cfg
    app.dependency_overrides[get_repo] = lambda: mock_repo
    app.dependency_overrides[get_player_id] = lambda: _FIXED_PLAYER_ID
    try:
        yield TestClient(app, raise_server_exceptions=False)
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
@allure.title("GET / exposes player-visible next-action suggestions in the core loop")
def test_get_index_exposes_next_action_suggestions(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == _HTTP_OK
    assert 'id="next-actions"' in response.text
    assert 'data-action="look around"' in response.text
    assert 'data-action="talk to someone nearby"' in response.text
    assert 'data-action="check my inventory"' in response.text


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


@allure.story("Current game lookup")
@allure.title("GET /api/games/current hides unexpected service exceptions from players")
def test_current_game_hides_unexpected_exception_detail(non_raising_client: TestClient) -> None:
    secret = "provider traceback: SECRET_API_KEY=sk-test"
    with patch.object(service, "get_current_snapshot", new=AsyncMock(side_effect=RuntimeError(secret))):
        response = non_raising_client.get("/api/games/current")
    assert response.status_code == _HTTP_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "Something went wrong. Please try again."}
    assert secret not in response.text


@allure.story("Current game lookup")
@allure.title("GET /api/games/current hides database exception details from players")
def test_current_game_hides_database_exception_detail(non_raising_client: TestClient) -> None:
    secret = "database traceback: password=super-secret"
    with patch.object(service, "get_current_snapshot", new=AsyncMock(side_effect=RuntimeError(secret))):
        response = non_raising_client.get("/api/games/current")
    assert response.status_code == _HTTP_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "Something went wrong. Please try again."}
    assert secret not in response.text


# ---------------------------------------------------------------------------
# POST /api/games
# ---------------------------------------------------------------------------


def _params_from_call(start_mock: AsyncMock) -> service.StartGameParams:
    """Extract the ``StartGameParams`` argument from a patched start_game_for_player call."""
    await_args = start_mock.await_args
    assert await_args is not None
    return next(arg for arg in await_args.args if isinstance(arg, service.StartGameParams))


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
    params = _params_from_call(start_mock)
    assert params.player_id == _FIXED_PLAYER_ID
    assert params.language == "Russian"
    assert params.setting == "Rome"
    assert params.character is None


@allure.story("Start game")
@allure.title("POST /api/games defaults the language to English when the body omits it")
def test_start_game_defaults_language_to_english(client: TestClient) -> None:
    snapshot = _sample_snapshot()
    start_mock = AsyncMock(return_value=snapshot)
    with patch.object(service, "start_game_for_player", new=start_mock):
        response = client.post("/api/games", json={"setting": "Rome"})
    assert response.status_code == _HTTP_CREATED
    params = _params_from_call(start_mock)
    assert params.language == "English"


@allure.story("Start game")
@allure.title("POST /api/games forwards the character payload through StartGameParams to the service")
def test_start_game_forwards_character_payload(client: TestClient) -> None:
    snapshot = _sample_snapshot()
    start_mock = AsyncMock(return_value=snapshot)
    payload = {
        "setting": "Rome",
        "character": {
            "name": "Alex",
            "appearance": "grey hoodie",
            "inventory": ["phone", " keys ", ""],
        },
    }
    with patch.object(service, "start_game_for_player", new=start_mock):
        response = client.post("/api/games", json=payload)
    assert response.status_code == _HTTP_CREATED
    params = _params_from_call(start_mock)
    assert params.character is not None
    assert params.character.name == "Alex"
    assert params.character.appearance == "grey hoodie"
    # Validator trims whitespace and drops empty items.
    assert params.character.inventory == ["phone", "keys"]


@allure.story("Start game")
@allure.title("GET /api/character-template returns the canned template character")
def test_get_character_template(client: TestClient) -> None:
    response = client.get("/api/character-template")
    assert response.status_code == _HTTP_OK
    body = response.json()
    assert "appearance" in body
    assert "inventory" in body
    assert body["appearance"]
    assert isinstance(body["inventory"], list)
    assert body["inventory"]


@allure.story("Start game")
@allure.title("POST /api/games rejects an inventory item longer than the per-item cap")
def test_start_game_rejects_oversize_inventory_item(client: TestClient) -> None:
    payload = {
        "setting": "Rome",
        "character": {"inventory": ["x" * 65]},
    }
    response = client.post("/api/games", json=payload)
    assert response.status_code == _HTTP_UNPROCESSABLE


@allure.story("Start game")
@allure.title("POST /api/games rejects an empty setting with HTTP 422")
def test_start_game_rejects_empty_setting(client: TestClient) -> None:
    response = client.post("/api/games", json={"setting": ""})
    assert response.status_code == _HTTP_UNPROCESSABLE


@allure.story("Start game")
@allure.title("POST /api/games hides provider exception details from players")
def test_start_game_hides_provider_exception_detail(non_raising_client: TestClient) -> None:
    secret = "provider traceback: OPENAI_API_KEY=sk-secret"
    with patch.object(service, "start_game_for_player", new=AsyncMock(side_effect=RuntimeError(secret))):
        response = non_raising_client.post("/api/games", json={"setting": "Rome"})
    assert response.status_code == _HTTP_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "Something went wrong. Please try again."}
    assert secret not in response.text


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


@allure.story("Player smoke")
@allure.title("Web API smoke starts a story and plays five turns with an NPC interaction and no raw traceback")
def test_player_web_api_smoke_start_five_turns_and_npc_interaction(client: TestClient) -> None:
    start_snapshot = _sample_snapshot(game_id="smoke-game")
    actions = [
        "look around",
        "walk to the tavern",
        "talk to Pieter about the missing map",
        "ask Pieter to describe the stranger",
        "thank Pieter and wait",
    ]
    turn_responses = [
        _smoke_turn_response("Pieter studies the street from the archway.", 1),
        _smoke_turn_response("You reach the tavern door as Pieter follows.", 2),
        _smoke_turn_response("Pieter says the map vanished before dawn.", 3),
        _smoke_turn_response("Pieter describes a cloaked stranger with a silver ring.", 4),
        _smoke_turn_response("Pieter nods while the room settles into watchful quiet.", 5),
    ]
    start_mock = AsyncMock(return_value=start_snapshot)
    process_mock = AsyncMock(side_effect=turn_responses)

    with (
        patch.object(service, "start_game_for_player", new=start_mock),
        patch.object(service, "process_turn_for_player", new=process_mock),
    ):
        start_response = client.post("/api/games", json={"setting": "Delft, 1665", "language": "English"})
        action_responses = [
            client.post(f"/api/games/{start_snapshot.game_id}/actions", json={"action": action}) for action in actions
        ]

    assert start_response.status_code == _HTTP_CREATED
    assert [response.status_code for response in action_responses] == [_HTTP_OK for _action in actions]
    assert process_mock.await_count == len(actions)
    assert [call.args[4] for call in process_mock.await_args_list] == actions
    assert "Pieter" in action_responses[2].json()["narration"]
    assert action_responses[-1].json()["turn_count"] == 5
    _assert_no_raw_traceback([start_response.text, *(response.text for response in action_responses)])


def _smoke_turn_response(narration: str, turn_count: int) -> ActionResponse:
    return ActionResponse(
        narration=narration,
        narration_html=render_narrator_html(narration),
        turn_count=turn_count,
        character=_empty_character(),
    )


def _assert_no_raw_traceback(payloads: list[str]) -> None:
    forbidden_fragments = ("Traceback (most recent call last)", "</traceback>", "RuntimeError:")
    for payload in payloads:
        assert not any(fragment in payload for fragment in forbidden_fragments)


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
        new=AsyncMock(side_effect=service.GameNotFoundError(_FIXED_PLAYER_ID)),
    ):
        response = client.post("/api/games/other-game/actions", json={"action": "look"})
    assert response.status_code == _HTTP_NOT_FOUND
    assert response.json()["detail"] == "No active game"


@allure.story("Submit action")
@allure.title("POST /api/games/{id}/actions hides provider exception details from players")
def test_post_action_hides_provider_exception_detail(non_raising_client: TestClient) -> None:
    secret = "provider traceback: AnthropicError(secret-token)"
    with patch.object(service, "process_turn_for_player", new=AsyncMock(side_effect=RuntimeError(secret))):
        response = non_raising_client.post("/api/games/game-abc/actions", json={"action": "look"})
    assert response.status_code == _HTTP_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "Something went wrong. Please try again."}
    assert secret not in response.text


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
@allure.title("process_turn_for_player raises GameNotFoundError when game_id does not match the loaded game")
async def test_process_turn_enforces_ownership() -> None:
    repo = AsyncMock()
    repo.sessions = MagicMock()
    repo.sessions.get_latest_web = AsyncMock(return_value={"id": "sess-1", "language": "English"})

    loaded_state = MagicMock()
    loaded_state.uuid = "real-game-id"
    repo.load_game_state.return_value = (loaded_state, MagicMock(), [])

    with pytest.raises(service.GameNotFoundError):
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
@allure.title("_act_and_persist raises RuntimeError when the engine is not started")
async def test_act_and_persist_raises_when_engine_has_no_game_state() -> None:
    """Guards the invariant: an un-started engine raises rather than silently returning 0."""
    repo = AsyncMock()
    engine = MagicMock()
    engine.assert_running = MagicMock(side_effect=RuntimeError("Game not started."))
    engine.process_action = AsyncMock(return_value="prose")

    with pytest.raises(RuntimeError, match="Game not started"):
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

    game_state = MagicMock()
    game_state.uuid = "game-1"
    game_state.setting.name = "Rome"
    game_state.conversation_log = []
    game_state.turn_count = 0
    game_state.scene_number = None
    game_state.player = MagicMock(
        name="Player",
        appearance="",
        physical_status="healthy",
        inventory=[],
        known_npcs=set(),
        player_event_log=[],
        learned_facts=set(),
    )
    # MagicMock coerces the kwarg ``name`` to the mock's own name; re-set it explicitly.
    game_state.player.name = "Player"
    game_state.npcs = {}

    engine = MagicMock()
    engine.start_game = AsyncMock()
    engine.assert_running = MagicMock(return_value=(game_state, MagicMock(), MagicMock(all_events=[])))

    start_request = service.StartGameParams(
        player_id=_FIXED_PLAYER_ID,
        setting="Rome",
        language="English",
    )
    with (
        patch("engine.session_ops.create_engine", return_value=engine),
        patch("engine.session_ops.load_role_overrides", new=AsyncMock(return_value={})),
    ):
        await service.start_game_for_player(repo=repo, cfg=MagicMock(), start_request=start_request)
        await service.start_game_for_player(repo=repo, cfg=MagicMock(), start_request=start_request)

    create_calls = repo.sessions.create_web.await_args_list
    assert len(create_calls) == 2
    assert all(call.args == (_FIXED_PLAYER_ID,) for call in create_calls)
    save_calls = repo.save_game_state.await_args_list
    assert {call.args[0] for call in save_calls} == {"sess-1", "sess-2"}
