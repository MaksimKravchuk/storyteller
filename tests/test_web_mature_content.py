"""Tests for the account-level 18+ (mature content) switch: API, persistence call, and moderation wiring."""

from __future__ import annotations

from typing import Iterator
from unittest import mock

import allure
import pytest
from fastapi.testclient import TestClient

from config import Config
from interfaces.web import schemas, service
from interfaces.web.app import app
from interfaces.web.auth_models import PlayerFeedbackContext, SupabaseClaims
from interfaces.web.deps import get_cfg, get_player_id, get_repo
from tests.test_web_auth import _auth_headers, _snapshot

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Mature content"),
]

_ACCOUNT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_USER_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_EMAIL = "player@example.com"


class _Stop(Exception):
    """Ends the service call right after the engine config is captured."""


def _account(mature_content: bool) -> dict[str, object]:
    return {
        "id": _ACCOUNT_ID,
        "supabase_user_id": _USER_ID,
        "email": _EMAIL,
        "plan": "friend_beta",
        "is_admin": False,
        "mature_content": mature_content,
    }


@pytest.fixture
def repo() -> mock.MagicMock:
    repo = mock.MagicMock(name="repo")
    repo.accounts = mock.AsyncMock(name="accounts")
    repo.accounts.is_email_invited.return_value = True
    repo.accounts.get_or_create_for_invited_user.return_value = _account(mature_content=True)
    return repo


@pytest.fixture
def client(repo: mock.MagicMock, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    cfg = Config(
        beta_auth_required=True,
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test_key",
        supabase_jwks_url="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        supabase_jwt_issuer="https://example.supabase.co/auth/v1",
    )
    claims = SupabaseClaims(sub=_USER_ID, email=_EMAIL)
    monkeypatch.setattr("interfaces.web.auth.verify_supabase_token", mock.AsyncMock(return_value=claims))
    app.dependency_overrides[get_cfg] = lambda: cfg
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_player_id] = lambda: "11111111-1111-1111-1111-111111111111"
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def open_beta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the service past the beta gates without a database."""
    monkeypatch.setattr(service.beta_policy.BetaPolicy, "ensure_open", mock.AsyncMock())
    monkeypatch.setattr(service.beta_policy.BetaPolicy, "ensure_turn_quota", mock.AsyncMock())
    monkeypatch.setattr(service.beta_policy.BetaPolicy, "ensure_active_game_quota", mock.AsyncMock())


@allure.story("Account API")
@allure.title("GET /api/me reports the account's mature-content switch")
def test_me_reports_mature_content(client: TestClient) -> None:
    response = client.get("/api/me", headers=_auth_headers())

    assert response.json()["mature_content"] is True


@allure.story("Account API")
@allure.title("PUT /api/me/preferences stores the switch on the account and echoes it back")
def test_preferences_update_stores_switch(client: TestClient, repo: mock.MagicMock) -> None:
    response = client.put("/api/me/preferences", json={"mature_content": False}, headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["mature_content"] is False
    repo.accounts.set_mature_content.assert_awaited_once_with(_ACCOUNT_ID, False)


@allure.story("Account API")
@allure.title("PUT /api/me/preferences requires a signed-in account")
def test_preferences_update_requires_auth(client: TestClient, repo: mock.MagicMock) -> None:
    response = client.put("/api/me/preferences", json={"mature_content": True})

    assert response.status_code == 401
    repo.accounts.set_mature_content.assert_not_awaited()


@allure.story("Moderation wiring")
@allure.title("POST /api/games hands the account's switch to the start-game service")
def test_start_game_route_passes_switch(client: TestClient) -> None:
    start = mock.AsyncMock(return_value=_snapshot())
    with mock.patch.object(service, "start_game_for_player", new=start):
        client.post("/api/games", json={"setting": "Rome"}, headers=_auth_headers())

    params = start.await_args_list[0].args[2]
    assert params.mature_content is True


@allure.story("Moderation wiring")
@allure.title("A new game for an 18+ account builds its engine with mature-content moderation")
@pytest.mark.asyncio
@pytest.mark.usefixtures("open_beta")
async def test_start_game_engine_gets_mature_config() -> None:
    begin = mock.AsyncMock(side_effect=_Stop)
    repo = mock.MagicMock()
    repo.sessions.create_web = mock.AsyncMock(return_value={"id": "s-1"})
    params = service.StartGameParams(player_id=_ACCOUNT_ID, setting="Rome", language="English", mature_content=True)

    with mock.patch.object(service, "begin_session", new=begin), pytest.raises(_Stop):
        await service.start_game_for_player(repo, Config(), params)

    engine_cfg = begin.await_args_list[0].args[1]
    assert engine_cfg.safety_mature_content is True


@allure.story("Moderation wiring")
@allure.title("A turn's engine gets mature-content moderation only when the player opted in")
@pytest.mark.asyncio
@pytest.mark.usefixtures("open_beta")
@pytest.mark.parametrize("mature_content", [True, False])
async def test_turn_engine_follows_player_switch(mature_content: bool) -> None:
    resume = mock.AsyncMock(side_effect=_Stop)
    owned = mock.AsyncMock(return_value=("s-1", "English"))
    player = PlayerFeedbackContext(player_id=_ACCOUNT_ID, email=_EMAIL, mature_content=mature_content)

    with (
        mock.patch.object(service, "resume_session", new=resume),
        mock.patch.object(
            service,
            "owned_session_context",
            new=owned,
        ),
        pytest.raises(_Stop),
    ):
        await service.process_turn_for_player(
            mock.MagicMock(), Config(), player, "g-1", schemas.ActionRequest(action="wait")
        )

    engine_cfg = resume.await_args_list[0].args[1]
    assert engine_cfg.safety_mature_content is mature_content


@allure.story("Static shell")
@allure.title("The static shell ships the account dialog with the 18+ switch wired to the preferences API")
def test_static_shell_has_mature_switch(client: TestClient) -> None:
    index = client.get("/").text
    script = client.get("/static/app.js").text

    assert 'id="account-btn"' in index
    assert 'id="mature-content"' in index
    assert '"/api/me/preferences"' in script
