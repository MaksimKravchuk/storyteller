"""Verb plans with minimal or no target data (Sleep / Wait / Explore / Other).

Split out of ``cast/schemas/action_plan.py`` so each sub-module stays
under the flake8 module-member budget.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from cast.schemas._action_plan_base import _PlanBase


class SleepPlan(_PlanBase):
    """The player sleeps, waits a long time, or otherwise ends the scene."""

    action_type: Literal["SLEEP"] = "SLEEP"


class WaitPlan(_PlanBase):
    """The player passes the turn without acting."""

    action_type: Literal["WAIT"] = "WAIT"
    wait_reason: str | None = Field(
        default=None,
        description=(
            "Why the player is waiting (e.g. 'voluntary', 'stunned'). "
            "Set by the forced-wait short-circuit; otherwise leave null."
        ),
    )


class ExplorePlan(_PlanBase):
    """The player looks around or surveys their surroundings (no move)."""

    action_type: Literal["EXPLORE"] = "EXPLORE"
    targets: list[str] = Field(
        default_factory=list,
        description="Specific things the player is scanning for, if any.",
    )


class OtherPlan(_PlanBase):
    """Catch-all for actions that do not fit any named verb."""

    action_type: Literal["OTHER"] = "OTHER"
    reason: str = Field(
        description=("Short explanation of what the player is attempting, for the narrator to improvise around."),
    )
    targets: list[str] = Field(default_factory=list)
    is_aggressive: bool = False
