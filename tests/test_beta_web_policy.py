"""Tests for web beta quota and kill-switch gates."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from config import Config
from defaults.entitlements import USER_PLAN_ADMIN, USER_PLAN_FRIEND_BETA, quota_settings_for_plan
from interfaces.web import service
from interfaces.web.beta_policy import BetaAccessDeniedError
from interfaces.web.auth_models import PlayerFeedbackContext
from interfaces.web.schemas import ActionRequest

_PLAYER_ID = "11111111-1111-1111-1111-111111111111"
_GAME_ID = "22222222-2222-2222-2222-222222222222"

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
    allure.story("Beta quotas"),
]


def _quota_repo() -> Any:
    ai_logs = SimpleNamespace(
        usage_summary=AsyncMock(return_value=[]),
        turn_count_for_user=AsyncMock(return_value=0),
    )
    sessions = SimpleNamespace(
        count_active_web=AsyncMock(return_value=0),
        create_web=AsyncMock(return_value={"id": "session-1", "language": "English"}),
    )
    return SimpleNamespace(ai_logs=ai_logs, sessions=sessions)


@pytest.mark.asyncio
@allure.title("Disabled beta blocks start before session creation or engine invocation")
async def test_beta_disabled_blocks_start_before_session_or_engine() -> None:
    repo = _quota_repo()
    cfg = Config(beta_enabled=False, beta_kill_message="Beta is paused.")
    start_request = service.StartGameParams(player_id=_PLAYER_ID, setting="Rome", language="English")

    begin_mock = AsyncMock()
    with patch.object(service, "begin_session", new=begin_mock):
        with pytest.raises(service.BetaAccessDeniedError, match="Beta is paused"):
            await service.start_game_for_player(repo, cfg, start_request)

    repo.sessions.create_web.assert_not_awaited()
    begin_mock.assert_not_awaited()


@pytest.mark.asyncio
@allure.title("Max active games quota blocks start before create_web")
async def test_max_active_games_blocks_start_before_create_web() -> None:
    repo = _quota_repo()
    repo.sessions.count_active_web.return_value = 3
    cfg = Config(beta_max_active_games=3)
    start_request = service.StartGameParams(player_id=_PLAYER_ID, setting="Rome", language="English")

    with pytest.raises(service.BetaAccessDeniedError) as exc_info:
        await service.start_game_for_player(repo, cfg, start_request)

    assert exc_info.value.reason == "max_active_games"
    repo.sessions.create_web.assert_not_awaited()


@pytest.mark.asyncio
@allure.title("Daily turn quota blocks action before engine resume")
async def test_daily_turn_quota_blocks_action_before_resume() -> None:
    repo = _quota_repo()
    repo.ai_logs.turn_count_for_user.return_value = 20
    cfg = Config(beta_daily_turn_quota=20)

    resume_mock = AsyncMock()
    with patch.object(service, "resume_session", new=resume_mock):
        with pytest.raises(service.BetaAccessDeniedError) as exc_info:
            await service.process_turn_for_player(repo, cfg, _PLAYER_ID, _GAME_ID, ActionRequest(action="look"))

    assert exc_info.value.reason == "daily_turn_quota"
    resume_mock.assert_not_awaited()


@pytest.mark.asyncio
@allure.title("Allowed action reaches resume after beta quota checks")
async def test_allowed_action_reaches_resume_after_quota_checks() -> None:
    repo = _quota_repo()
    repo.web_games = MagicMock()
    repo.web_games.get_by_game = AsyncMock(return_value={"id": "session-1", "language": "English"})
    cfg = Config()

    resume_mock = AsyncMock(return_value=None)
    with patch.object(service, "resume_session", new=resume_mock):
        with pytest.raises(service.GameNotFoundError):
            await service.process_turn_for_player(repo, cfg, _PLAYER_ID, _GAME_ID, ActionRequest(action="look"))

    assert repo.ai_logs.turn_count_for_user.await_count == 2
    resume_mock.assert_awaited_once()


@pytest.mark.asyncio
@allure.title("Global budget exhaustion blocks action before engine resume")
async def test_global_budget_blocks_action_before_resume() -> None:
    repo = _quota_repo()
    repo.ai_logs.usage_summary.return_value = [
        {
            "user_id": _PLAYER_ID,
            "session_id": "session-1",
            "game_state_id": _GAME_ID,
            "utc_day": "2026-05-24",
            "model": "gpt-5.4-mini",
            "prompt_tokens": 1_000_000,
            "completion_tokens": 500_000,
            "call_count": 1,
            "missing_usage_count": 0,
            "started_at": None,
            "ended_at": None,
        },
    ]
    cfg = Config(beta_global_budget_usd="1.25")

    resume_mock = AsyncMock()
    with patch.object(service, "resume_session", new=resume_mock):
        with pytest.raises(service.BetaAccessDeniedError) as exc_info:
            await service.process_turn_for_player(repo, cfg, _PLAYER_ID, _GAME_ID, ActionRequest(action="look"))

    assert exc_info.value.reason == "global_budget_exhausted"
    resume_mock.assert_not_awaited()


@pytest.mark.asyncio
@allure.title("Friend beta plan uses configured quota settings")
async def test_friend_beta_plan_uses_configured_quota_settings() -> None:
    repo = _quota_repo()
    repo.sessions.count_active_web.return_value = 2
    cfg = Config(beta_max_active_games=2, beta_daily_turn_quota=7, beta_weekly_turn_quota=11)
    quotas = quota_settings_for_plan(cfg, USER_PLAN_FRIEND_BETA)

    with pytest.raises(service.BetaAccessDeniedError) as exc_info:
        await service.start_game_for_player(
            repo,
            cfg,
            service.StartGameParams(
                player_id=_PLAYER_ID,
                plan=USER_PLAN_FRIEND_BETA,
                setting="Rome",
                language="English",
            ),
        )

    assert quotas.daily_turn_quota == 7
    assert quotas.weekly_turn_quota == 11
    assert quotas.max_active_games == 2
    assert exc_info.value.reason == "max_active_games"
    repo.sessions.create_web.assert_not_awaited()


@pytest.mark.asyncio
@allure.title("Admin plan bypasses per-user game and turn quotas")
async def test_admin_plan_bypasses_per_user_quotas() -> None:
    repo = _quota_repo()
    repo.sessions.count_active_web.return_value = 99
    repo.ai_logs.turn_count_for_user.return_value = 99
    cfg = Config(beta_max_active_games=1, beta_daily_turn_quota=1, beta_weekly_turn_quota=1)
    quotas = quota_settings_for_plan(cfg, USER_PLAN_ADMIN)

    policy = service.beta_policy.BetaPolicy(repo, cfg)
    await policy.ensure_active_game_quota(_PLAYER_ID, USER_PLAN_ADMIN)
    await policy.ensure_turn_quota(_PLAYER_ID, USER_PLAN_ADMIN)

    assert quotas.daily_turn_quota is None
    assert quotas.weekly_turn_quota is None
    assert quotas.max_active_games is None
    repo.sessions.count_active_web.assert_not_awaited()
    repo.ai_logs.turn_count_for_user.assert_not_awaited()


@allure.title("Authenticated player context carries a deterministic default plan")
def test_player_context_defaults_to_friend_beta_plan() -> None:
    context = PlayerFeedbackContext(player_id=_PLAYER_ID, email=None)

    assert context.plan == USER_PLAN_FRIEND_BETA


@pytest.mark.asyncio
@allure.title("BetaPolicy no longer skips the kill switch for a mock config")
async def test_policy_does_not_bypass_checks_for_mock_config() -> None:
    cfg = MagicMock()
    cfg.beta_enabled = False
    cfg.beta_kill_message = "closed"

    with pytest.raises(BetaAccessDeniedError) as exc_info:
        await service.beta_policy.BetaPolicy(_quota_repo(), cfg).ensure_open()

    assert exc_info.value.reason == "beta_disabled"
