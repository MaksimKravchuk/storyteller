"""Typed action-routing schemas used by the Director.

The Director classifies each player turn by calling exactly one of the
provider tools derived from these Pydantic models.
:data:`ActionPlan` is a ``Annotated[Union[...], Field(discriminator)]``
over eight verb-specific shapes; :class:`ClarificationRequest` is a
separate return type the Director short-circuits on when the LLM needs
more info from the player.

Verb classes and the shared base live in private sub-modules
(``_action_plan_base``, ``_action_plan_verbs_targeted``,
``_action_plan_verbs_simple``) so each module stays within the flake8
module-member budget. Consumers should import from here.
"""

from __future__ import annotations

from typing import Annotated, Union

from pydantic import BaseModel, ConfigDict, Field

from cast.schemas._action_plan_base import Contest as _Contest
from cast.schemas._action_plan_verbs_simple import ExplorePlan, OtherPlan, SleepPlan, WaitPlan
from cast.schemas._action_plan_verbs_targeted import ExaminePlan, InteractPlan, MovePlan, TalkPlan

# Re-exported under the canonical name for external callers (tests, director_execution).
Contest = _Contest

ActionPlan = Annotated[
    Union[
        MovePlan,
        TalkPlan,
        ExaminePlan,
        InteractPlan,
        SleepPlan,
        WaitPlan,
        ExplorePlan,
        OtherPlan,
    ],
    Field(discriminator="action_type"),
]


class ClarificationRequest(BaseModel):
    """Returned when the LLM cannot route an action without more info.

    Not part of :data:`ActionPlan` — the Director branches on type and
    short-circuits the turn, returning the question to the player
    without advancing the game clock.
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(description="Question to ask the player, phrased in their language.")
    reason: str = Field(
        default="",
        description=("Short rationale for the ambiguity (e.g. 'two NPCs named Marcus'). Not shown to the player."),
    )
