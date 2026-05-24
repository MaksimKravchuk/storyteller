"""Tests for Supabase-backed beta auth and invite gating in the web API."""

from __future__ import annotations

from typing import Iterator
from unittest import mock

import allure
import pytest
from fastapi.testclient import TestClient

from config import Config
from interfaces.web import auth, schemas, service
from interfaces.web.app import app
from interfaces.web.auth_models import SupabaseClaims
from interfaces.web.deps import get_cfg, get_player_id, get_repo
from interfaces.web.transcript import render_narrator_html

_HTTP_OK = 200
_HTTP_CREATED = 201
_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403

_ACCOUNT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_LEGACY_PLAYER_ID = "11111111-1111-1111-1111-111111111111"
_VALID_TOKEN = "valid.jwt.token"
_USER_EMAIL = "Invited@Example.COM"
_USER_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI Auth"),
]


@pytest.fixture
def auth_cfg() -> Config:
    """Return an auth-required config using only public Supabase env-style values."""
    return Config(
        beta_auth_required=True,
        beta_invite_gate_enabled=True,
        supabase_url="https://example.supabase.co",
        supabase_anon_key="public-anon-key",
        supabase_jwks_url="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        supabase_jwt_issuer="https://example.supabase.co/auth/v1",
    )


@pytest.fixture
def mock_repo() -> mock.MagicMock:
    repo = mock.MagicMock(name="repo")
    repo.accounts = mock.AsyncMock(name="accounts")
    repo.accounts.is_email_invited.return_value = True
    repo.accounts.get_or_create_for_invited_user.return_value = {
        "id": _ACCOUNT_ID,
        "supabase_user_id": _USER_ID,
        "email": _USER_EMAIL.lower(),
        "plan": "friend_beta",
        "is_admin": False,
    }
    return repo


@pytest.fixture
def client(auth_cfg: Config, mock_repo: mock.MagicMock) -> Iterator[TestClient]:
    app.dependency_overrides[get_cfg] = lambda: auth_cfg
    app.dependency_overrides[get_repo] = lambda: mock_repo
    app.dependency_overrides[get_player_id] = lambda: _LEGACY_PLAYER_ID
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _auth_headers(token: str = _VALID_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clear_jwks_client_cache() -> Iterator[None]:
    auth._get_supabase_jwks_client.cache_clear()
    try:
        yield
    finally:
        auth._get_supabase_jwks_client.cache_clear()


def _snapshot() -> schemas.GameSnapshot:
    text = "The gate opens."
    return schemas.GameSnapshot(
        game_id="game-abc",
        setting="Rome",
        transcript=[schemas.TurnEntry(role="narrator", text=text, html=render_narrator_html(text))],
        turn_count=0,
        character=schemas.CharacterInfo(
            name="Player",
            appearance="",
            physical_status="healthy",
            inventory=[],
            known_npcs=[],
            recent_events=[],
            learned_facts=[],
        ),
    )


@allure.story("Authenticated user metadata")
@allure.title("GET /api/me returns 401 when beta auth is required and no bearer token is present")
def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/me")

    assert response.status_code == _HTTP_UNAUTHORIZED
    assert response.json()["detail"] == "Authentication required"


@allure.story("Authenticated user metadata")
@allure.title("GET /api/me returns 401 for a malformed bearer header")
def test_me_rejects_malformed_bearer_header(client: TestClient) -> None:
    response = client.get("/api/me", headers={"Authorization": "Token not-a-bearer"})

    assert response.status_code == _HTTP_UNAUTHORIZED
    assert response.json()["detail"] == "Malformed Authorization header"


@allure.story("Invite gate")
@allure.title("POST /api/games returns 403 for authenticated users who are not invited")
def test_start_game_rejects_uninvited_user_without_calling_service(
    client: TestClient,
    mock_repo: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_repo.accounts.is_email_invited.return_value = False
    verify_mock = mock.AsyncMock(return_value=SupabaseClaims(sub=_USER_ID, email=_USER_EMAIL))
    monkeypatch.setattr("interfaces.web.auth.verify_supabase_token", verify_mock)
    start_mock = mock.AsyncMock(return_value=_snapshot())

    with mock.patch.object(service, "start_game_for_player", new=start_mock):
        response = client.post("/api/games", json={"setting": "Rome"}, headers=_auth_headers())

    assert response.status_code == _HTTP_FORBIDDEN
    assert response.json()["detail"] == "Invite required"
    verify_mock.assert_awaited_once()
    start_mock.assert_not_awaited()


@allure.story("Authenticated user metadata")
@allure.title("GET /api/me returns account metadata for an invited Supabase user")
def test_me_returns_invited_account_metadata(
    client: TestClient,
    mock_repo: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_mock = mock.AsyncMock(return_value=SupabaseClaims(sub=_USER_ID, email=_USER_EMAIL))
    monkeypatch.setattr("interfaces.web.auth.verify_supabase_token", verify_mock)

    response = client.get("/api/me", headers=_auth_headers())

    assert response.status_code == _HTTP_OK
    assert response.json() == {
        "account_id": _ACCOUNT_ID,
        "email": _USER_EMAIL.lower(),
        "plan": "friend_beta",
        "is_admin": False,
    }
    mock_repo.accounts.is_email_invited.assert_awaited_once_with(_USER_EMAIL)
    mock_repo.accounts.get_or_create_for_invited_user.assert_awaited_once_with(_USER_ID, _USER_EMAIL)


@allure.story("Start game")
@allure.title("POST /api/games uses the local account UUID as player id for invited users")
def test_start_game_uses_account_id_for_invited_user(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_mock = mock.AsyncMock(return_value=SupabaseClaims(sub=_USER_ID, email=_USER_EMAIL))
    monkeypatch.setattr("interfaces.web.auth.verify_supabase_token", verify_mock)
    start_mock = mock.AsyncMock(return_value=_snapshot())

    with mock.patch.object(service, "start_game_for_player", new=start_mock):
        response = client.post("/api/games", json={"setting": "Rome"}, headers=_auth_headers())

    assert response.status_code == _HTTP_CREATED
    start_mock.assert_awaited_once()
    await_args = start_mock.await_args
    assert await_args is not None
    params = next(arg for arg in await_args.args if isinstance(arg, service.StartGameParams))
    assert params.player_id == _ACCOUNT_ID


@allure.story("Auth failures")
@allure.title("POST /api/games returns 401 and does not call the service when JWT verification fails")
def test_start_game_rejects_invalid_token_without_calling_service(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_mock = mock.AsyncMock(side_effect=ValueError("bad token"))
    monkeypatch.setattr("interfaces.web.auth.verify_supabase_token", verify_mock)
    start_mock = mock.AsyncMock(return_value=_snapshot())

    with mock.patch.object(service, "start_game_for_player", new=start_mock):
        response = client.post("/api/games", json={"setting": "Rome"}, headers=_auth_headers("bad.jwt"))

    assert response.status_code == _HTTP_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid authentication token"
    start_mock.assert_not_awaited()


@allure.story("Auth failures")
@allure.title("GET /api/character-template requires bearer auth when beta auth is required")
def test_character_template_requires_auth_when_beta_auth_required(client: TestClient) -> None:
    response = client.get("/api/character-template")

    assert response.status_code == _HTTP_UNAUTHORIZED
    assert response.json()["detail"] == "Authentication required"


@allure.story("Start game")
@allure.title("GET /api/character-template returns template for an authenticated invited user")
def test_character_template_allows_authenticated_invited_user(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_mock = mock.AsyncMock(return_value=SupabaseClaims(sub=_USER_ID, email=_USER_EMAIL))
    monkeypatch.setattr("interfaces.web.auth.verify_supabase_token", verify_mock)

    response = client.get("/api/character-template", headers=_auth_headers())

    assert response.status_code == _HTTP_OK
    assert response.json()["appearance"]
    verify_mock.assert_awaited_once()


@allure.story("JWT verification")
@allure.title("Supabase JWT verification reuses a cached JWKS client with bounded fetch timeout")
@pytest.mark.asyncio
async def test_verify_supabase_token_caches_jwks_client_with_timeout(
    auth_cfg: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signing_key = mock.Mock()
    signing_key.key = "public-key"
    jwks_client = mock.Mock()
    jwks_client.get_signing_key_from_jwt.return_value = signing_key
    client_factory = mock.Mock(return_value=jwks_client)
    decode_mock = mock.Mock(return_value={"sub": _USER_ID, "email": _USER_EMAIL})
    monkeypatch.setattr(auth, "PyJWKClient", client_factory)
    monkeypatch.setattr(auth.pyjwt, "decode", decode_mock)

    first = await auth.verify_supabase_token(_VALID_TOKEN, auth_cfg)
    second = await auth.verify_supabase_token(_VALID_TOKEN, auth_cfg)

    assert first == second == SupabaseClaims(sub=_USER_ID, email=_USER_EMAIL)
    client_factory.assert_called_once_with(
        str(auth_cfg.supabase_jwks_url),
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=300,
        timeout=5.0,
    )
    jwks_client.get_signing_key_from_jwt.assert_has_calls([mock.call(_VALID_TOKEN), mock.call(_VALID_TOKEN)])
    assert jwks_client.get_signing_key_from_jwt.call_count == 2
    assert decode_mock.call_count == 2


@allure.story("JWT verification")
@allure.title("Supabase JWT verification propagates JWKS fetch errors without decoding")
@pytest.mark.asyncio
async def test_verify_supabase_token_propagates_jwks_errors_without_decoding(
    auth_cfg: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jwks_client = mock.Mock()
    jwks_client.get_signing_key_from_jwt.side_effect = TimeoutError("jwks timed out")
    client_factory = mock.Mock(return_value=jwks_client)
    decode_mock = mock.Mock(name="decode")
    monkeypatch.setattr(auth, "PyJWKClient", client_factory)
    monkeypatch.setattr(auth.pyjwt, "decode", decode_mock)

    with pytest.raises(TimeoutError, match="jwks timed out"):
        await auth.verify_supabase_token(_VALID_TOKEN, auth_cfg)

    client_factory.assert_called_once_with(
        str(auth_cfg.supabase_jwks_url),
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=300,
        timeout=5.0,
    )
    decode_mock.assert_not_called()


@allure.story("Runtime public config")
@allure.title("GET /api/config/public exposes only public Supabase auth settings")
def test_public_config_exposes_public_supabase_values_only(client: TestClient) -> None:
    response = client.get("/api/config/public")

    assert response.status_code == _HTTP_OK
    assert response.json() == {
        "supabase_url": "https://example.supabase.co",
        "supabase_anon_key": "public-anon-key",
        "beta_auth_required": True,
        "beta_invite_gate_enabled": True,
    }
    assert "jwks" not in response.text.lower()
    assert "issuer" not in response.text.lower()


@allure.story("Static shell")
@allure.title("Static UI includes Supabase login/logout controls and auth fetch wiring")
def test_static_shell_includes_auth_controls(client: TestClient) -> None:
    index_response = client.get("/")
    script_response = client.get("/static/app.js")

    assert index_response.status_code == _HTTP_OK
    assert script_response.status_code == _HTTP_OK
    assert 'id="auth-panel"' in index_response.text
    assert 'id="login-email"' in index_response.text
    assert 'id="logout-btn"' in index_response.text
    assert "supabase-js" in index_response.text
    assert "signInWithOtp" in script_response.text
    assert "Authorization" in script_response.text
