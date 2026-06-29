"""Plan names and quota entitlements for beta accounts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, cast

from config import Config

UserPlan = Literal["friend_beta", "admin"]
USER_PLAN_FRIEND_BETA: UserPlan = "friend_beta"
USER_PLAN_ADMIN: UserPlan = "admin"
DEFAULT_USER_PLAN: UserPlan = USER_PLAN_FRIEND_BETA

ALLOWED_USER_PLANS: frozenset[UserPlan] = frozenset((USER_PLAN_FRIEND_BETA, USER_PLAN_ADMIN))


@dataclass(frozen=True)
class PlanQuotaSettings:
    """Per-plan gameplay quota settings.

    ``None`` means the plan is not capped by that per-user quota. Global beta
    kill switch and budget checks still apply outside this structure.
    """

    daily_turn_quota: int | None
    weekly_turn_quota: int | None
    max_active_games: int | None


def normalize_user_plan(plan: object) -> UserPlan:
    """Return a supported plan value, defaulting safely for missing or invalid rows."""
    if plan in ALLOWED_USER_PLANS:
        return cast("UserPlan", plan)
    return DEFAULT_USER_PLAN


def quota_settings_for_plan(cfg: Config, plan: object) -> PlanQuotaSettings:
    """Return centralized quota settings for a user plan."""
    return _quota_settings_by_plan(cfg)[normalize_user_plan(plan)]


def _quota_settings_by_plan(cfg: Config) -> Mapping[UserPlan, PlanQuotaSettings]:
    """Build the dynamic quota table from runtime config values."""
    return {
        USER_PLAN_FRIEND_BETA: PlanQuotaSettings(
            daily_turn_quota=cfg.beta_daily_turn_quota,
            weekly_turn_quota=cfg.beta_weekly_turn_quota,
            max_active_games=cfg.beta_max_active_games,
        ),
        USER_PLAN_ADMIN: PlanQuotaSettings(
            daily_turn_quota=None,
            weekly_turn_quota=None,
            max_active_games=None,
        ),
    }
