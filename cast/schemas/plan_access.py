"""Attribute accessors for :data:`cast.schemas.action_plan.ActionPlan` variants.

Not every verb plan carries every field (``WaitPlan`` has no ``targets``,
``SleepPlan`` has no ``is_aggressive``, etc.). These helpers centralise
the ``getattr`` defaults so consumer code treats all variants uniformly.
"""

from __future__ import annotations

from typing import Any

from cast.schemas import action_plan as plan_mod


def targets(plan: Any) -> list[str]:
    """Return the plan's targets list, or ``[]`` for verbs that have none."""
    return list(getattr(plan, "targets", ()) or ())


def is_aggressive(plan: Any) -> bool:
    """Return the plan's ``is_aggressive`` flag if present, else False."""
    return bool(getattr(plan, "is_aggressive", False))


def delegate_to(plan: Any) -> list[str]:
    """Return the plan's ``delegate_to`` list, normalised to a plain list."""
    return list(getattr(plan, "delegate_to", ()) or ())


def contest(plan: Any) -> plan_mod.Contest | None:
    """Return the plan's ``contest`` attribute, or None when the verb has none."""
    return getattr(plan, "contest", None)


def contest_as_dict(plan: Any) -> dict[str, Any] | None:
    """Return the plan's contest serialised as a dict for legacy consumers.

    :class:`cast.director_dialogue.DialogueHandler.handle_dialogue` still
    accepts the pre-typed-plan ``dict`` shape. Centralising the
    ``model_dump()`` call here keeps that conversion out of the hot path
    in :mod:`cast.director_execution`.
    """
    contested = contest(plan)
    return None if contested is None else contested.model_dump()
