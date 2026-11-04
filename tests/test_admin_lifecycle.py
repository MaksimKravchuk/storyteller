"""Tests for the admin router mounted in the player FastAPI app: routing and the auth gate."""

from __future__ import annotations

from unittest.mock import MagicMock

import allure
import httpx
import pytest

from config import Config
from interfaces.web.app import create_app
from interfaces.web import deps

_HTTP_OK = 200
_HTTP_UNAUTHORIZED = 401

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin dashboard"),
]


def _client(cfg: Config) -> httpx.AsyncClient:
    app = create_app()
    app.dependency_overrides[deps.get_cfg] = MagicMock(return_value=cfg)
    app.dependency_overrides[deps.get_session_factory] = MagicMock(return_value=MagicMock())
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@allure.story("Mounting")
@allure.title("The player app serves the admin dashboard at /admin and /admin/")
@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/admin", "/admin/"])
async def test_dashboard_is_served_by_player_app(path: str) -> None:
    async with _client(Config(beta_auth_required=True)) as client:
        resp = await client.get(path)
    assert resp.status_code == _HTTP_OK
    assert "text/html" in resp.headers["content-type"]


@allure.story("Mounting")
@allure.title("Admin /api/* is gated by auth in the player app, while the player /healthz stays open")
@pytest.mark.asyncio
async def test_admin_api_gated_in_player_app() -> None:
    async with _client(Config(beta_auth_required=True)) as client:
        assert (await client.get("/admin/api/sessions")).status_code == _HTTP_UNAUTHORIZED
        assert (await client.get("/healthz")).status_code == _HTTP_OK
