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

from interfaces.web import auth_models, beta_auth, player_gestures, runtime, service, service_feedback
from interfaces.web.app import app
from interfaces.web.deps import get_cfg, get_player_id, get_repo
from interfaces.web.character_schemas import CharacterInfo
from interfaces.web.schemas import (
    ActionRequest,
    ActionResponse,
    GameSnapshot,
    PlayerGesture,
    TurnEntry,
    WorldView,
)

from interfaces.web.transcript import (
    build_transcript,
    render_narrator_html,
    render_player_html,
)

_HTTP_OK = 200
_HTTP_CREATED = 201
_HTTP_ACCEPTED = 202
_HTTP_NOT_FOUND = 404
_HTTP_INTERNAL_SERVER_ERROR = 500
_HTTP_SERVICE_UNAVAILABLE = 503
_HTTP_UNPROCESSABLE = 422

_FIXED_PLAYER_ID = "11111111-1111-1111-1111-111111111111"
_ANOTHER_PLAYER_ID = "22222222-2222-2222-2222-222222222222"

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]


@pytest.fixture(autouse=True)
def _beta_policy_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests pass a mock cfg; stub the gates (BetaPolicy itself is tested with a real Config)."""
    for gate in ("ensure_open", "ensure_turn_quota", "ensure_active_game_quota"):
        monkeypatch.setattr(service.beta_policy.BetaPolicy, gate, AsyncMock())


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


def _empty_world() -> WorldView:
    return WorldView.model_validate(
        {
            "map": {"current": None, "connections": [], "breadcrumb": []},
            "people": [],
            "clock": {"day": 1, "time_of_day": "morning", "hour": 0},
        },
    )


def _sample_world() -> WorldView:
    return WorldView.model_validate(
        {
            "map": {
                "current": {"id": "loc-forum", "name": "Forum Romanum", "location_type": "district"},
                "connections": [{"id": "loc-tavern", "name": "The Tavern", "location_type": "building"}],
                "breadcrumb": [{"id": "loc-rome", "name": "Rome", "location_type": "city"}],
            },
            "people": [{"label": "a stern guard", "role": "guard", "known": False}],
            "clock": {"day": 2, "time_of_day": "afternoon", "hour": 14},
        },
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
        world=_sample_world(),
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
@allure.title("GET / exposes the Story/Character/Map tab bar for the play screen")
def test_get_index_exposes_play_tabbar(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == _HTTP_OK
    assert 'id="tabbar"' in response.text
    assert 'data-pane="story"' in response.text
    assert 'data-pane="character"' in response.text
    assert 'data-pane="map"' in response.text
    # The "Try next" chips were removed when the play screen went interactive.
    assert 'id="next-actions"' not in response.text


@allure.story("Beta feedback")
@allure.title("GET / exposes the in-app beta feedback form")
def test_get_index_exposes_beta_feedback_form(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == _HTTP_OK
    assert 'id="feedback-form"' in response.text
    assert 'id="feedback-category"' in response.text
    assert 'id="feedback-message"' in response.text


@allure.story("Beta feedback")
@allure.title("POST /api/games/{game_id}/feedback submits owned game feedback with user context")
def test_post_feedback_submits_user_and_game_context(
    client: TestClient,
    mock_repo: AsyncMock,
    mock_cfg: MagicMock,
) -> None:
    app.dependency_overrides[beta_auth.get_beta_player_context] = lambda: auth_models.PlayerFeedbackContext(
        player_id=_FIXED_PLAYER_ID,
        email="friend@example.com",
    )
    submit_mock = AsyncMock(return_value="feedback-123")

    with patch.object(service_feedback, "submit_beta_feedback", new=submit_mock):
        response = client.post(
            "/api/games/game-abc/feedback",
            json={"category": "bug", "message": "The scene repeated after I acted."},
        )

    assert response.status_code == _HTTP_ACCEPTED
    assert response.json() == {"feedback_id": "feedback-123"}
    submit_mock.assert_awaited_once_with(
        mock_repo,
        mock_cfg,
        service_feedback.FeedbackSubmission(
            player_id=_FIXED_PLAYER_ID,
            email="friend@example.com",
            game_id="game-abc",
            category="bug",
            message="The scene repeated after I acted.",
        ),
    )


@allure.story("Beta feedback")
@allure.title("POST /api/games/{game_id}/feedback returns 404 for unowned games")
def test_post_feedback_rejects_unowned_game(client: TestClient) -> None:
    submit_mock = AsyncMock(side_effect=service.GameNotFoundError(_FIXED_PLAYER_ID))

    with patch.object(service_feedback, "submit_beta_feedback", new=submit_mock):
        response = client.post(
            "/api/games/foreign-game/feedback",
            json={"category": "bug", "message": "This should not attach."},
        )

    assert response.status_code == _HTTP_NOT_FOUND
    assert response.json()["detail"] == "No active game"


@allure.story("Beta feedback")
@allure.title("POST /api/games/{game_id}/feedback rejects blank messages")
def test_post_feedback_rejects_blank_message(client: TestClient) -> None:
    response = client.post(
        "/api/games/game-abc/feedback",
        json={"category": "bug", "message": "   "},
    )

    assert response.status_code == 422


@allure.story("Beta feedback")
@allure.title("Feedback service verifies game ownership before storing feedback")
@pytest.mark.asyncio
async def test_submit_beta_feedback_requires_owned_game(mock_repo: AsyncMock, mock_cfg: MagicMock) -> None:
    mock_repo.web_games.get_by_game.return_value = None
    mock_repo.feedback.create = AsyncMock()

    with pytest.raises(service.GameNotFoundError):
        await service_feedback.submit_beta_feedback(
            mock_repo,
            mock_cfg,
            service_feedback.FeedbackSubmission(
                player_id=_FIXED_PLAYER_ID,
                email="friend@example.com",
                game_id="foreign-game",
                category="bug",
                message="This should not attach.",
            ),
        )

    mock_repo.web_games.get_by_game.assert_awaited_once_with(_FIXED_PLAYER_ID, "foreign-game")
    mock_repo.feedback.create.assert_not_awaited()


@allure.story("Static shell")
@allure.title("GET / explains the AI demo and provides example first setting prompts")
def test_get_index_explains_first_time_setting_prompt(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == _HTTP_OK
    assert "AI text quest demo" in response.text
    assert "Tell Storyteller where and when the adventure should begin" in response.text
    assert response.text.count("data-setting-example=") >= 3


@allure.story("Static shell")
@allure.title("Static web client uses understandable loading-state copy")
def test_static_client_explains_loading_states(client: TestClient) -> None:
    index_response = client.get("/")
    script_response = client.get("/static/app.js")
    assert index_response.status_code == _HTTP_OK
    assert script_response.status_code == _HTTP_OK
    assert "Checking for an existing quest" in index_response.text
    assert "Building your AI text quest demo" in script_response.text
    assert "The AI narrator is resolving your action" in script_response.text


@allure.story("Static shell")
@allure.title("GET / exposes PWA metadata, service worker registration, and offline copy")
def test_get_index_exposes_pwa_metadata_and_offline_notice(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == _HTTP_OK
    assert '<link rel="manifest" href="/manifest.webmanifest" />' in response.text
    assert '<meta name="theme-color" content="#13100d" />' in response.text
    assert 'id="offline-banner"' in response.text
    assert "Storyteller needs an internet connection and model access to continue." in response.text

    app_js = client.get("/static/app.js")
    assert app_js.status_code == _HTTP_OK
    assert "serviceWorker" in app_js.text
    assert 'navigator.serviceWorker.register("/sw.js")' in app_js.text


@allure.story("Static shell")
@allure.title("GET /manifest.webmanifest serves installable app metadata")
def test_get_manifest_serves_installable_metadata(client: TestClient) -> None:
    response = client.get("/manifest.webmanifest")

    assert response.status_code == _HTTP_OK
    assert "application/manifest+json" in response.headers["content-type"]
    manifest = response.json()
    assert manifest["name"] == "Storyteller"
    assert manifest["short_name"] == "Storyteller"
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["theme_color"] == "#13100d"
    assert manifest["background_color"] == "#13100d"
    assert {icon["src"] for icon in manifest["icons"]} == {
        "/static/icons/icon-192.png",
        "/static/icons/icon-512.png",
    }


@allure.story("Static shell")
@allure.title("GET /sw.js serves a service worker that keeps gameplay online-required")
def test_get_service_worker_serves_online_required_worker(client: TestClient) -> None:
    response = client.get("/sw.js")

    assert response.status_code == _HTTP_OK
    assert "text/javascript" in response.headers["content-type"]
    assert "STORYTELLER-PWA-CACHE" in response.text
    assert "Storyteller needs an internet connection and model access to continue." in response.text
    assert 'requestPath(request).startsWith("/api/")' in response.text
    assert "PRECACHE_URLS.includes(requestPath(request))" in response.text
    assert "caches.open" in response.text
    # Cross-origin calls (Supabase auth) must reach the network untouched, not the offline stub.
    assert "url.origin !== self.location.origin" in response.text


@allure.story("Static shell")
@allure.title("GET /healthz returns 200 with a status:ok body and does not touch the repo")
def test_healthz_returns_ok(client: TestClient, mock_repo) -> None:
    response = client.get("/healthz")
    assert response.status_code == _HTTP_OK
    assert response.json() == {"status": "ok"}
    # Liveness probe must not consult the DB.
    mock_repo.sessions.get_latest_web.assert_not_called()


@allure.story("Runtime readiness")
@allure.title("GET /readyz reports ok when every configured LLM provider has a key")
def test_readyz_returns_ok_when_required_provider_keys_are_present(
    client: TestClient,
    mock_cfg: MagicMock,
    mock_repo,
) -> None:
    mock_cfg.director_model = "gpt-5.4-mini"
    mock_cfg.agent_model = "gpt-5.4-nano"
    mock_cfg.narrator_model = "gpt-5.4-mini"
    mock_cfg.dramaturge_model = "gpt-5.4-nano"
    mock_cfg.dramaturge_enabled = False
    mock_cfg.openai_api_key = "sk-present"
    mock_cfg.anthropic_api_key = None
    mock_cfg.openrouter_api_key = None
    mock_cfg.deepseek_api_key = None

    response = client.get("/readyz")

    assert response.status_code == _HTTP_OK
    assert response.json() == {
        "status": "ok",
        "required_providers": ["openai"],
        "missing_providers": [],
    }
    mock_repo.sessions.get_latest_web.assert_not_called()


@allure.story("Runtime readiness")
@allure.title("GET /readyz fails when a configured LLM provider has no key")
def test_readyz_returns_503_when_required_provider_key_is_missing(
    client: TestClient,
    mock_cfg: MagicMock,
) -> None:
    mock_cfg.director_model = "claude-sonnet-4"
    mock_cfg.agent_model = "claude-haiku-4-5"
    mock_cfg.narrator_model = "claude-sonnet-4"
    mock_cfg.dramaturge_model = "claude-haiku-4-5"
    mock_cfg.dramaturge_enabled = False
    mock_cfg.openai_api_key = None
    mock_cfg.anthropic_api_key = None
    mock_cfg.openrouter_api_key = None
    mock_cfg.deepseek_api_key = None

    response = client.get("/readyz")

    assert response.status_code == _HTTP_SERVICE_UNAVAILABLE
    assert response.json() == {
        "status": "unavailable",
        "required_providers": ["anthropic"],
        "missing_providers": ["anthropic"],
        "detail": "Storyteller is not ready to start games: missing LLM provider credentials.",
    }


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
    # Consumer seam: the WorldView reaches the snapshot JSON on load.
    world_map = body["world"]["map"]
    assert world_map["current"]["name"] == "Forum Romanum"
    assert world_map["breadcrumb"][0]["name"] == "Rome"
    assert body["world"]["clock"]["day"] == 2


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
# My Stories library
# ---------------------------------------------------------------------------


@allure.story("My Stories")
@allure.title("GET /api/games lists only the caller's games")
def test_list_games_returns_current_player_library(client: TestClient, mock_repo) -> None:
    list_response = {"games": [{"game_id": "game-1", "title": "Rome", "setting": "Rome", "turn_count": 2}]}
    list_mock = AsyncMock(return_value=list_response)
    with patch("interfaces.web.routes_library.service_library.list_games_for_player", new=list_mock):
        response = client.get("/api/games")
    assert response.status_code == _HTTP_OK
    assert response.json()["games"] == [
        {
            "game_id": "game-1",
            "title": "Rome",
            "setting": "Rome",
            "turn_count": 2,
            "playbill": None,
            "has_poster_image": False,
        },
    ]
    list_mock.assert_awaited_once_with(mock_repo, _FIXED_PLAYER_ID)


class _OwnedWebGames:
    """Small in-memory web-game store that enforces owner filtering like SQL."""

    def __init__(self) -> None:
        self._rows = {
            _FIXED_PLAYER_ID: [
                {"game_id": "game-1", "title": "Rome", "setting": "Rome", "turn_count": 2},
            ],
            _ANOTHER_PLAYER_ID: [
                {"game_id": "game-2", "title": "Mars", "setting": "Mars", "turn_count": 1},
            ],
        }
        self.archived: list[tuple[str, str]] = []

    async def list(self, player_id: str) -> list[dict[str, object]]:
        """Return only rows owned by ``player_id``."""
        return list(self._rows.get(player_id, []))

    async def archive(self, player_id: str, game_id: str) -> bool:
        """Archive only caller-owned rows."""
        owned_rows = self._rows.get(player_id, [])
        if not any(row["game_id"] == game_id for row in owned_rows):
            return False
        self.archived.append((player_id, game_id))
        return True


class _OwnedLibraryRepo:
    """Repository double that lets route tests exercise service_library."""

    def __init__(self) -> None:
        self.web_games = _OwnedWebGames()
        self.commit = AsyncMock()


@pytest.fixture
def owned_library_client(mock_cfg) -> Iterator[tuple[TestClient, _OwnedLibraryRepo]]:
    """Return a client backed by a fake owner-enforcing repository."""
    repo = _OwnedLibraryRepo()
    app.dependency_overrides[get_cfg] = lambda: mock_cfg
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_player_id] = lambda: "cookie-player"
    app.dependency_overrides[beta_auth.get_beta_player_id] = lambda: _FIXED_PLAYER_ID
    try:
        yield TestClient(app), repo
    finally:
        app.dependency_overrides.clear()


@allure.story("My Stories")
@allure.title("GET /api/games uses beta account id and excludes other users' stories")
def test_list_games_uses_account_id_for_ownership(
    owned_library_client: tuple[TestClient, _OwnedLibraryRepo],
) -> None:
    test_client, _repo = owned_library_client

    response = test_client.get("/api/games")

    assert response.status_code == _HTTP_OK
    assert [(game["game_id"], game["title"], game["turn_count"]) for game in response.json()["games"]] == [
        ("game-1", "Rome", 2),
    ]


@allure.story("My Stories")
@allure.title("POST /api/games/{id}/archive hides another user's story id")
def test_archive_game_enforces_account_ownership(
    owned_library_client: tuple[TestClient, _OwnedLibraryRepo],
) -> None:
    test_client, repo = owned_library_client

    response = test_client.post("/api/games/game-2/archive")

    assert response.status_code == _HTTP_NOT_FOUND
    assert response.json()["detail"] == "No active game"
    repo.commit.assert_not_awaited()


@allure.story("My Stories")
@allure.title("POST /api/games/{id}/archive commits the caller's own story")
def test_archive_game_commits_owned_story(
    owned_library_client: tuple[TestClient, _OwnedLibraryRepo],
) -> None:
    test_client, repo = owned_library_client

    response = test_client.post("/api/games/game-1/archive")

    assert response.status_code == 204
    assert repo.web_games.archived == [(_FIXED_PLAYER_ID, "game-1")]
    repo.commit.assert_awaited_once()


@allure.story("My Stories")
@allure.title("GET /api/games/{id} returns one owned game snapshot")
def test_get_game_happy_path(client: TestClient) -> None:
    snapshot = _sample_snapshot(game_id="game-1")
    get_mock = AsyncMock(return_value=snapshot)
    with patch("interfaces.web.routes_library.service_library.get_snapshot_for_player_game", new=get_mock):
        response = client.get("/api/games/game-1")
    assert response.status_code == _HTTP_OK
    body = response.json()
    assert body["game_id"] == "game-1"
    # Consumer seam: continuing a story serves the WorldView through the route.
    assert body["world"]["map"]["current"]["name"] == "Forum Romanum"
    assert get_mock.await_args is not None
    assert get_mock.await_args.args[2:] == (_FIXED_PLAYER_ID, "game-1")


@allure.story("My Stories")
@allure.title("GET /api/games/{id} returns 404 for absent or foreign games")
def test_get_game_hides_ownership_violations(client: TestClient) -> None:
    get_mock = AsyncMock(return_value=None)
    with patch("interfaces.web.routes_library.service_library.get_snapshot_for_player_game", new=get_mock):
        response = client.get("/api/games/foreign-game")
    assert response.status_code == _HTTP_NOT_FOUND
    assert response.json()["detail"] == "No active game"
    assert get_mock.await_args is not None
    assert get_mock.await_args.args[2:] == (_FIXED_PLAYER_ID, "foreign-game")


@allure.story("My Stories")
@allure.title("POST /api/games/{id}/archive returns 404 for absent or foreign games")
def test_archive_game_hides_ownership_violations(client: TestClient) -> None:
    archive_mock = AsyncMock(return_value=False)
    with patch("interfaces.web.routes_library.service_library.archive_game_for_player", new=archive_mock):
        response = client.post("/api/games/foreign-game/archive")
    assert response.status_code == _HTTP_NOT_FOUND
    assert response.json()["detail"] == "No active game"
    assert archive_mock.await_args is not None
    assert archive_mock.await_args.args[1:] == (_FIXED_PLAYER_ID, "foreign-game")


@allure.story("My Stories")
@allure.title("POST /api/games/{id}/archive returns 204 when the caller owns the game")
def test_archive_game_happy_path(client: TestClient) -> None:
    archive_mock = AsyncMock(return_value=True)
    with patch("interfaces.web.routes_library.service_library.archive_game_for_player", new=archive_mock):
        response = client.post("/api/games/game-1/archive")
    assert response.status_code == 204
    assert response.content == b""
    assert archive_mock.await_args is not None
    assert archive_mock.await_args.args[1:] == (_FIXED_PLAYER_ID, "game-1")


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
    body = response.json()
    assert body["game_id"] == snapshot.game_id
    # Consumer seam: the opening snapshot carries the WorldView for the dashboard.
    assert body["world"]["map"]["current"]["name"] == "Forum Romanum"
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
@allure.title("POST /api/games returns a player-safe 503 when the LLM provider rejects credentials")
def test_start_game_returns_503_for_provider_auth_failure(client: TestClient) -> None:
    secret = "provider traceback: OPENAI_API_KEY=sk-secret"
    with patch.object(
        service,
        "start_game_for_player",
        new=AsyncMock(side_effect=service.GameStartUnavailableError(secret)),
    ):
        response = client.post("/api/games", json={"setting": "Rome"})

    assert response.status_code == _HTTP_SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": "Storyteller is temporarily unable to start games. Please try again later.",
    }
    assert secret not in response.text


@allure.story("Start game")
@allure.title("POST /api/games returns a player-safe 503 when game start fails at runtime")
def test_start_game_returns_503_for_runtime_start_failure(client: TestClient) -> None:
    secret = "runtime traceback: password=super-secret"
    with patch.object(
        service,
        "start_game_for_player",
        new=AsyncMock(side_effect=service.GameStartFailedError(secret)),
    ):
        response = client.post("/api/games", json={"setting": "Rome"})

    assert response.status_code == _HTTP_SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": "Storyteller could not start this game. Please try another premise or try again.",
    }
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
        world=_sample_world(),
    )
    process_mock = AsyncMock(return_value=action_response)
    with patch.object(service, "process_turn_for_player", new=process_mock):
        response = client.post("/api/games/game-abc/actions", json={"action": "look"})
    assert response.status_code == _HTTP_OK
    body = response.json()
    assert body["narration"] == "**Pieter** waves."
    assert body["narration_html"] == "<p><strong>Pieter</strong> waves.</p>"
    assert body["turn_count"] == 3
    # Consumer seam: the WorldView reaches the action response JSON, not just the DTO.
    world_map = body["world"]["map"]
    assert world_map["current"]["name"] == "Forum Romanum"
    assert world_map["connections"][0]["name"] == "The Tavern"
    assert body["world"]["people"][0]["label"] == "a stern guard"
    assert body["world"]["clock"] == {"day": 2, "time_of_day": "afternoon", "hour": 14}


@allure.story("Submit action")
@allure.title("POST /api/games/{id}/actions accepts a structured gesture and returns action_html")
def test_post_action_accepts_gesture(client: TestClient) -> None:
    action_response = ActionResponse(
        narration="Marcus turns to you.",
        narration_html=render_narrator_html("Marcus turns to you."),
        action_html="talk to Marcus",
        turn_count=1,
        character=_empty_character(),
        world=_sample_world(),
    )
    process_mock = AsyncMock(return_value=action_response)
    with patch.object(service, "process_turn_for_player", new=process_mock):
        response = client.post(
            "/api/games/game-abc/actions",
            json={"gesture": {"intent": "talk", "entity_kind": "npc", "entity_id": "npc-1"}},
        )
    assert response.status_code == _HTTP_OK
    assert response.json()["action_html"] == "talk to Marcus"
    # The route hands the whole ActionRequest (carrying the gesture) to the service.
    assert process_mock.await_args is not None
    request_arg = process_mock.await_args.args[4]
    assert isinstance(request_arg, ActionRequest)
    assert request_arg.gesture == PlayerGesture(intent="talk", entity_kind="npc", entity_id="npc-1")


@allure.story("Submit action")
@allure.title("POST /api/games/{id}/actions rejects an invalid intent×kind gesture at the request boundary")
def test_post_action_rejects_invalid_gesture_pair(client: TestClient) -> None:
    response = client.post(
        "/api/games/game-abc/actions",
        json={"gesture": {"intent": "talk", "entity_kind": "poi", "entity_id": "poi-1"}},
    )
    assert response.status_code == _HTTP_UNPROCESSABLE


@allure.story("Submit action")
@allure.title("POST /api/games/{id}/actions maps an unresolvable gesture to 422")
def test_post_action_gesture_resolution_error_maps_to_422(client: TestClient) -> None:
    process_mock = AsyncMock(side_effect=player_gestures.GestureResolutionError("stale id"))
    with patch.object(service, "process_turn_for_player", new=process_mock):
        response = client.post(
            "/api/games/game-abc/actions",
            json={"gesture": {"intent": "move", "entity_kind": "location", "entity_id": "gone"}},
        )
    assert response.status_code == _HTTP_UNPROCESSABLE


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
    assert [call.args[4].action for call in process_mock.await_args_list] == actions
    assert "Pieter" in action_responses[2].json()["narration"]
    assert action_responses[-1].json()["turn_count"] == 5
    _assert_no_raw_traceback([start_response.text, *(response.text for response in action_responses)])


def _smoke_turn_response(narration: str, turn_count: int) -> ActionResponse:
    return ActionResponse(
        narration=narration,
        narration_html=render_narrator_html(narration),
        turn_count=turn_count,
        character=_empty_character(),
        world=_empty_world(),
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
@allure.title("POST /api/games/{id}/actions returns a player-safe 503 when provider auth fails")
def test_post_action_returns_503_for_provider_auth_failure(client: TestClient) -> None:
    secret = "provider traceback: AnthropicError(secret-token)"
    with patch.object(
        service,
        "process_turn_for_player",
        new=AsyncMock(side_effect=service.GameStartUnavailableError(secret)),
    ):
        response = client.post("/api/games/game-abc/actions", json={"action": "look"})

    assert response.status_code == _HTTP_SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": "Storyteller is temporarily unable to start games. Please try again later.",
    }
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
    repo.web_games = MagicMock()
    repo.web_games.get_by_game = AsyncMock(return_value=None)

    with pytest.raises(service.GameNotFoundError):
        await service.process_turn_for_player(
            repo=repo,
            cfg=MagicMock(),
            player_id=_ANOTHER_PLAYER_ID,
            game_id="wrong-game-id",
            request=ActionRequest(action="look"),
        )


@pytest.mark.asyncio
@allure.story("Ownership enforcement")
@allure.title("process_turn_for_player raises GameNotFoundError when the player has no saved game")
async def test_process_turn_raises_when_no_game() -> None:
    repo = AsyncMock()
    repo.web_games = MagicMock()
    repo.web_games.get_by_game = AsyncMock(return_value={"id": "sess-1", "language": "English"})
    repo.load_game_state.return_value = None

    with pytest.raises(service.GameNotFoundError):
        await service.process_turn_for_player(
            repo=repo,
            cfg=MagicMock(),
            player_id=_FIXED_PLAYER_ID,
            game_id="game-abc",
            request=ActionRequest(action="look"),
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


class _NonMonotonicTurnEngine:
    """Test double that appends actions while exposing non-monotonic engine counts."""

    def __init__(self, game_state: MagicMock) -> None:
        self._game_state = game_state
        self._underlying_counts = [0, 1, 1]
        self._narrations = ["You look around.", "You think it over.", "You wait."]

    async def process_action(self, action: str) -> str:
        self._game_state.turn_count = self._underlying_counts.pop(0)
        narration = self._narrations.pop(0)
        self._game_state.conversation_log.append(
            {
                "player_action": action,
                "response": narration,
                "turn": self._game_state.turn_count,
            },
        )
        return narration

    def assert_running(self) -> tuple[MagicMock, MagicMock, MagicMock]:
        return self._game_state, MagicMock(), MagicMock(all_events=[])


@pytest.mark.asyncio
@allure.story("Submit action")
@allure.title("ActionPersistence returns monotonic player-visible turn counts")
async def test_act_and_persist_returns_monotonic_player_visible_turn_counts() -> None:
    repo = AsyncMock()
    game_state = MagicMock()
    game_state.uuid = "game-abc"
    game_state.setting.name = "Rome"
    game_state.conversation_log = [{"response": "Opening scene.", "turn": 0}]
    game_state.turn_count = 0
    game_state.last_visible_entities = []
    game_state.player = MagicMock(
        appearance="",
        physical_status="healthy",
        inventory=[],
        known_npcs=set(),
        player_event_log=[],
        learned_facts=set(),
    )
    game_state.player.name = "Player"
    game_state.player.location_id = None
    game_state.npcs = {}
    game_state.locations = {}
    game_state.current_scene = None
    game_state.game_clock = float(0)
    game_state.game_time = "morning"

    snapshot_engine = MagicMock()
    snapshot_engine.assert_running = MagicMock(return_value=(game_state, MagicMock(), MagicMock(all_events=[])))
    engine = _NonMonotonicTurnEngine(game_state)
    opening_turn_count = service.snapshot_from_engine(snapshot_engine).turn_count

    with patch.object(runtime, "persist_engine_state", new=AsyncMock()) as persist_mock:
        first_response = await service._act_and_persist(repo, "sess-1", engine, "look", "English")
        second_response = await service._act_and_persist(repo, "sess-1", engine, "think", "English")
        third_response = await service._act_and_persist(repo, "sess-1", engine, "wait", "English")

    assert opening_turn_count == 0
    assert [first_response.turn_count, second_response.turn_count, third_response.turn_count] == [1, 2, 3]
    # The action the engine ran is echoed back HTML-escaped so gesture turns can render it.
    assert [first_response.action_html, second_response.action_html] == ["look", "think"]
    assert [call.kwargs["turn_number"] for call in persist_mock.await_args_list] == [0, 1, 1]


@pytest.mark.asyncio
@allure.story("Ownership enforcement")
@allure.title("process_turn_for_player raises GameNotFoundError when the player has no session row at all")
async def test_process_turn_raises_when_no_session() -> None:
    repo = AsyncMock()
    repo.web_games = MagicMock()
    repo.web_games.get_by_game = AsyncMock(return_value=None)

    with pytest.raises(service.GameNotFoundError):
        await service.process_turn_for_player(
            repo=repo,
            cfg=MagicMock(),
            player_id=_FIXED_PLAYER_ID,
            game_id="game-abc",
            request=ActionRequest(action="look"),
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
    repo.commit = AsyncMock()
    repo.save_game_state.return_value = None

    game_state = MagicMock()
    game_state.uuid = "game-1"
    game_state.setting.name = "Rome"
    game_state.setting.time_period = "1st century BC"
    game_state.setting.region = "Italy"
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
    game_state.player.location_id = None
    game_state.npcs = {}
    game_state.locations = {}
    game_state.current_scene = None
    game_state.game_clock = float(0)
    game_state.game_time = "morning"

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


@pytest.mark.asyncio
@allure.story("Start game")
@allure.title("start_game_for_player commits the created session before returning")
async def test_start_game_commits_before_returning_snapshot() -> None:
    repo = AsyncMock()
    repo.sessions = MagicMock()
    repo.sessions.create_web = AsyncMock(return_value={"id": "sess-1", "language": "English"})
    repo.sessions.update = AsyncMock()
    repo.commit = AsyncMock()
    repo.save_game_state.return_value = None

    game_state = MagicMock()
    game_state.uuid = "game-1"
    game_state.setting.name = "Rome"
    game_state.setting.time_period = "1st century BC"
    game_state.setting.region = "Italy"
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
    game_state.player.name = "Player"
    game_state.player.location_id = None
    game_state.npcs = {}
    game_state.locations = {}
    game_state.current_scene = None
    game_state.game_clock = float(0)
    game_state.game_time = "morning"

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

    repo.sessions.update.assert_awaited_once_with("sess-1", state="playing", language="English")
    # One commit for the session row (before paid LLM work), one for the playing state.
    assert repo.commit.await_count == 2


@pytest.mark.asyncio
@allure.story("Submit action")
@allure.title("process_turn_for_player commits the action before returning")
async def test_process_turn_commits_before_returning_response() -> None:
    repo = AsyncMock()
    repo.web_games = MagicMock()
    repo.web_games.get_by_game = AsyncMock(return_value={"id": "sess-1", "language": "English"})
    repo.commit = AsyncMock()

    game_state = MagicMock()
    game_state.uuid = "game-abc"
    game_state.turn_count = 1
    game_state.scene_number = None
    game_state.last_visible_entities = []
    game_state.player = MagicMock(
        name="Player",
        appearance="",
        physical_status="healthy",
        inventory=[],
        known_npcs=set(),
        player_event_log=[],
        learned_facts=set(),
    )
    game_state.player.name = "Player"
    game_state.player.location_id = None
    game_state.npcs = {}
    game_state.locations = {}
    game_state.current_scene = None
    game_state.game_clock = float(0)
    game_state.game_time = "morning"
    repo.load_game_state = AsyncMock(return_value=(game_state, MagicMock(), []))

    engine = MagicMock()
    engine.process_action = AsyncMock(return_value="You look around.")
    engine.assert_running = MagicMock(return_value=(game_state, MagicMock(), MagicMock(all_events=[])))

    with patch("engine.session_ops.restore_engine_with_admin_settings", new=AsyncMock(return_value=engine)):
        response = await service.process_turn_for_player(
            repo=repo,
            cfg=MagicMock(),
            player_id=_FIXED_PLAYER_ID,
            game_id="game-abc",
            request=ActionRequest(action="look"),
        )

    assert response.narration == "You look around."
    repo.commit.assert_awaited_once_with()


@pytest.mark.asyncio
@allure.story("Start game")
@allure.title("start_game_for_player raises GameStartUnavailableError when provider auth fails")
async def test_start_game_for_player_classifies_provider_auth_failure() -> None:
    repo = AsyncMock()
    repo.sessions = MagicMock()
    repo.sessions.create_web = AsyncMock(return_value={"id": "sess-1", "language": "English"})
    repo.sessions.update = AsyncMock()
    repo.rollback = AsyncMock()
    repo.sessions.archive = AsyncMock()

    engine = MagicMock()
    engine.start_game = AsyncMock(side_effect=RuntimeError("invalid_api_key: bad provider key"))

    start_request = service.StartGameParams(
        player_id=_FIXED_PLAYER_ID,
        setting="Rome",
        language="English",
    )

    with (
        patch("engine.session_ops.create_engine", return_value=engine),
        patch("engine.session_ops.load_role_overrides", new=AsyncMock(return_value={})),
    ):
        with pytest.raises(service.GameStartUnavailableError):
            await service.start_game_for_player(repo=repo, cfg=MagicMock(), start_request=start_request)

    repo.rollback.assert_awaited_once()
    repo.sessions.archive.assert_awaited_once_with("sess-1")
    repo.sessions.update.assert_not_awaited()
