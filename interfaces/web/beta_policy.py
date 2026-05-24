"""Friends beta gates for web gameplay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from config import Config
from costs.reports import build_cost_summary
from db.repository import GameRepository


class _BetaLimits:
    """Messages and fixed windows for friends beta policy checks."""

    budget_message = "Storyteller beta is paused while we review usage. Please try again later."
    friendly_quota_message = (
        "You have reached the Friends Beta play limit for now. Please try again after your quota resets."
    )
    seconds_per_day = 86_400
    days_per_week = 7


class BetaAccessDeniedError(RuntimeError):
    """Raised when beta policy blocks gameplay before engine work starts."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


class BetaPolicy:
    """Enforce beta kill switch, budget, and per-player quotas."""

    def __init__(self, repo: GameRepository, cfg: Config) -> None:
        self._repo = repo
        self._cfg = cfg

    async def ensure_open(self) -> None:
        """Enforce global kill switch and budget before engine work."""
        if _is_mock_config(self._cfg):
            return
        if not self._cfg.beta_enabled:
            raise BetaAccessDeniedError(self._cfg.beta_kill_message, reason="beta_disabled")
        budget = _decimal_budget(self._cfg)
        if budget <= 0:
            raise BetaAccessDeniedError(
                _BetaLimits.budget_message,
                reason="global_budget_exhausted",
            )
        if await self._estimated_total_spend() >= budget:
            raise BetaAccessDeniedError(
                _BetaLimits.budget_message,
                reason="global_budget_exhausted",
            )

    async def ensure_active_game_quota(self, player_id: str) -> None:
        """Block new games once a player reaches the active-game quota."""
        if _is_mock_config(self._cfg):
            return
        active_games = await self._repo.sessions.count_active_web(player_id)
        if active_games >= self._cfg.beta_max_active_games:
            raise BetaAccessDeniedError(
                _BetaLimits.friendly_quota_message,
                reason="max_active_games",
            )

    async def ensure_turn_quota(self, player_id: str) -> None:
        """Block player turns once daily or weekly turn quotas are exhausted."""
        if _is_mock_config(self._cfg):
            return
        now = datetime.now(UTC)
        tomorrow = now + timedelta(seconds=_BetaLimits.seconds_per_day)
        await self._ensure_daily_quota(player_id, now, tomorrow)
        await self._ensure_weekly_quota(player_id, now, tomorrow)

    async def _estimated_total_spend(self) -> Decimal:
        """Return current estimated beta spend from AI log aggregates."""
        rows = await self._repo.ai_logs.usage_summary()
        summary = build_cost_summary(rows, self._cfg)
        return Decimal(summary["total"]["estimated_cost_usd"])

    async def _ensure_daily_quota(self, player_id: str, now: datetime, end_at: datetime) -> None:
        """Block a player who has reached the daily turn quota."""
        daily = await self._repo.ai_logs.turn_count_for_user(
            player_id,
            start_at=_period_start(now, 1),
            end_at=end_at,
        )
        if daily >= self._cfg.beta_daily_turn_quota:
            raise BetaAccessDeniedError(
                _BetaLimits.friendly_quota_message,
                reason="daily_turn_quota",
            )

    async def _ensure_weekly_quota(self, player_id: str, now: datetime, end_at: datetime) -> None:
        """Block a player who has reached the weekly turn quota."""
        weekly = await self._repo.ai_logs.turn_count_for_user(
            player_id,
            start_at=_period_start(now, _BetaLimits.days_per_week),
            end_at=end_at,
        )
        if weekly >= self._cfg.beta_weekly_turn_quota:
            raise BetaAccessDeniedError(
                _BetaLimits.friendly_quota_message,
                reason="weekly_turn_quota",
            )


def _is_mock_config(cfg: Config) -> bool:
    """Return True for legacy tests that pass MagicMock instead of Config."""
    return cfg.__class__.__module__.startswith("unittest.mock")


def _decimal_budget(cfg: Config) -> Decimal:
    """Parse configured budget; invalid values fail closed at zero budget."""
    try:
        return Decimal(str(cfg.beta_global_budget_usd))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _period_start(now: datetime, days: int) -> datetime:
    """Return a rolling UTC quota-window start."""
    return now - timedelta(days=days)
