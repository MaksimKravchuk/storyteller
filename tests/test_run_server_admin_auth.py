"""The deployed admin server never boots without account-role auth."""

from __future__ import annotations

import allure
import pytest

import run_server
from config import Config

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin dashboard"),
    allure.story("Admin auth"),
]


@allure.title("On Fly, disabled beta auth aborts startup instead of serving an open admin API")
def test_fly_requires_beta_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLY_APP_NAME", "storyteller-quest")
    with pytest.raises(SystemExit):
        run_server.require_admin_auth_on_fly(Config(beta_auth_required=False))


@allure.title("On Fly, enabled beta auth boots; local runs boot without auth")
def test_admin_auth_guard_allows_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLY_APP_NAME", "storyteller-quest")
    run_server.require_admin_auth_on_fly(Config(beta_auth_required=True))
    monkeypatch.delenv("FLY_APP_NAME")
    run_server.require_admin_auth_on_fly(Config(beta_auth_required=False))
