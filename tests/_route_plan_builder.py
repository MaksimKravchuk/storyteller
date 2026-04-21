"""Test-fixture helper for building typed ActionPlan instances.

Split out of ``tests/director_helpers.py`` so the dispatch table + per-verb
construction stays in one place without tripping the module-member rules
on the shared fixtures file.
"""

from __future__ import annotations

import types
from dataclasses import dataclass
from typing import Any, Callable

from cast.schemas import action_plan as plan_mod
from cast.schemas._action_plan_base import Delegate


@dataclass(frozen=True)
class _PlanDefaults:
    """Bundle of per-verb fields with test-friendly defaults.

    Using attribute access (kw.intent, kw.targets) keeps flake8's
    overused-expression and string-literal rules happy compared to
    repeated ``kw["intent"]`` dict lookups.
    """

    intent: str
    delegate_to: list[Delegate]
    targets: list[str]
    is_aggressive: bool
    contest: plan_mod.Contest | None
    direction: str
    reason: str
    wait_reason: str | None


def _move(kw: _PlanDefaults) -> plan_mod.MovePlan:
    return plan_mod.MovePlan(
        intent=kw.intent,
        delegate_to=kw.delegate_to,
        direction=kw.direction,
        targets=kw.targets,
        is_aggressive=kw.is_aggressive,
    )


def _talk(kw: _PlanDefaults) -> plan_mod.TalkPlan:
    return plan_mod.TalkPlan(
        intent=kw.intent,
        delegate_to=kw.delegate_to,
        targets=kw.targets,
        is_aggressive=kw.is_aggressive,
        contest=kw.contest,
    )


def _examine(kw: _PlanDefaults) -> plan_mod.ExaminePlan:
    return plan_mod.ExaminePlan(intent=kw.intent, delegate_to=kw.delegate_to, targets=kw.targets)


def _interact(kw: _PlanDefaults) -> plan_mod.InteractPlan:
    return plan_mod.InteractPlan(
        intent=kw.intent,
        delegate_to=kw.delegate_to,
        targets=kw.targets,
        is_aggressive=kw.is_aggressive,
        contest=kw.contest,
    )


def _simple(kw: _PlanDefaults, action_type: str) -> Any:
    """Build one of the simple verbs (SLEEP / WAIT / EXPLORE / OTHER)."""
    if action_type == "SLEEP":
        return plan_mod.SleepPlan(intent=kw.intent, delegate_to=kw.delegate_to)
    if action_type == "WAIT":
        return plan_mod.WaitPlan(
            intent=kw.intent,
            delegate_to=kw.delegate_to,
            wait_reason=kw.wait_reason,
        )
    if action_type == "EXPLORE":
        return plan_mod.ExplorePlan(
            intent=kw.intent,
            delegate_to=kw.delegate_to,
            targets=kw.targets,
        )
    return plan_mod.OtherPlan(
        intent=kw.intent,
        delegate_to=kw.delegate_to,
        reason=kw.reason,
        targets=kw.targets,
        is_aggressive=kw.is_aggressive,
    )


_TARGETED_BUILDERS: types.MappingProxyType[str, Callable[[_PlanDefaults], Any]] = types.MappingProxyType(
    {
        "MOVE": _move,
        "TALK": _talk,
        "EXAMINE": _examine,
        "INTERACT": _interact,
    },
)


def build_route_plan(action_type: str, **overrides: Any) -> Any:
    """Build a typed ActionPlan / ClarificationRequest for Director tests.

    Accepts a string ``action_type`` (one of MOVE/TALK/EXAMINE/INTERACT/
    SLEEP/WAIT/EXPLORE/OTHER) and routes to the matching verb model,
    filling missing fields with test-friendly defaults. When
    ``clarify=True`` is passed, returns a ``ClarificationRequest`` instead.
    """
    if overrides.pop("clarify", False):
        return plan_mod.ClarificationRequest(
            question=overrides.get("clarify_q") or "Which one?",
            reason=overrides.get("reason") or "test",
        )
    kw = _PlanDefaults(
        intent=overrides.get("intent") or "test intent",
        delegate_to=list(overrides.get("delegate") or ("narrator",)),
        targets=list(overrides.get("targets") or ()),
        is_aggressive=bool(overrides.get("is_aggressive")),
        contest=overrides.get("contest"),
        direction=overrides.get("direction") or "forward",
        reason=overrides.get("reason") or "test",
        wait_reason=overrides.get("wait_reason"),
    )
    targeted = _TARGETED_BUILDERS.get(action_type)
    if targeted is not None:
        return targeted(kw)
    return _simple(kw, action_type)
