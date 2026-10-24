"""The deployed admin server never boots without an ``ADMIN_TOKEN``."""

from __future__ import annotations

import allure
import pytest

import run_server

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin dashboard"),
    allure.story("Admin auth"),
]


@allure.title("On Fly, a missing or empty ADMIN_TOKEN aborts startup instead of serving an open admin API")
@pytest.mark.parametrize("token", [None, ""])
def test_fly_requires_admin_token(monkeypatch: pytest.MonkeyPatch, token: str | None) -> None:
    monkeypatch.setenv("FLY_APP_NAME", "storyteller-quest")
    if token is None:
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ADMIN_TOKEN", token)
    with pytest.raises(SystemExit):
        run_server.admin_token()


@allure.title("Local runs keep the tokenless admin dashboard; a configured token is passed through")
def test_admin_token_outside_fly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    assert run_server.admin_token() is None
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    assert run_server.admin_token() == "secret"
