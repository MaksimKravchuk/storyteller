"""Shared base classes and type aliases for the action-plan schemas.

Split out of ``cast/schemas/action_plan.py`` so each sub-module stays
under the flake8 module-member budget. Consumers should import from
``cast.schemas.action_plan`` (which re-exports these names), not from
this private helper module.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Category literal for contested checks. Exposed so test fixtures and
# external consumers can annotate their own types.
ContestType = Literal["combat", "persuasion", "deception", "intimidation", "stealth"]

# Delegate labels the LLM may hand work off to. Kept closed so the
# provider rejects typos at the tool-schema layer.
Delegate = Literal[
    "scene_builder",
    "narrator",
    "actor",
    "npc_generator",
    "item_generator",
]


class Contest(BaseModel):
    """A contested check (combat / persuasion / ...) against a target.

    Only :class:`TalkPlan` and :class:`InteractPlan` carry this; for every
    other verb the field is absent from the tool schema entirely.
    """

    model_config = ConfigDict(extra="forbid")

    type: ContestType
    target: str = Field(description="NPC name the check is resolved against.")


class _PlanBase(BaseModel):
    """Fields shared across every action verb.

    Kept separate from the verb classes so the discriminator on
    :data:`cast.schemas.action_plan.ActionPlan` is the ``action_type``
    literal alone — Pydantic's discriminated union cannot disambiguate
    by anything else.
    """

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(
        description=("One-sentence, faithful restatement of the player's stated goal. Not your interpretation of it."),
    )
    delegate_to: list[Delegate] = Field(
        default_factory=list,
        description="Specialist agents the Director should invoke this turn.",
    )
    time_cost_override: float | None = Field(
        default=None,
        description=(
            "Override the default turn cost in hours. Leave null unless the "
            "default is clearly wrong for this specific action."
        ),
    )
