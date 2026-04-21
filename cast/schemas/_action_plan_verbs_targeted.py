"""Verb plans that carry a ``targets`` list (Move / Talk / Examine / Interact).

Split out of ``cast/schemas/action_plan.py`` so each sub-module stays
under the flake8 module-member budget.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from cast.schemas._action_plan_base import Contest, _PlanBase


class MovePlan(_PlanBase):
    """The player moves through the scene or to a nearby location."""

    action_type: Literal["MOVE"] = "MOVE"
    direction: str = Field(
        description=("Target location or direction as the player expressed it (e.g. 'market', 'north', 'upstairs')."),
    )
    targets: list[str] = Field(
        default_factory=list,
        description="NPC names the player intends to approach, if any.",
    )
    is_aggressive: bool = False


class TalkPlan(_PlanBase):
    """The player addresses one or more NPCs."""

    action_type: Literal["TALK"] = "TALK"
    targets: list[str] = Field(description="NPC names the player addresses this turn.")
    is_aggressive: bool = False
    contest: Contest | None = None


class ExaminePlan(_PlanBase):
    """The player looks closely at a specific object, item, or NPC feature."""

    action_type: Literal["EXAMINE"] = "EXAMINE"
    targets: list[str] = Field(description="Object, item, or NPC names the player examines.")


class InteractPlan(_PlanBase):
    """The player physically interacts with an object, item, or NPC."""

    action_type: Literal["INTERACT"] = "INTERACT"
    targets: list[str] = Field(description="Object or NPC names the player interacts with.")
    is_aggressive: bool = False
    contest: Contest | None = None
