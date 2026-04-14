"""Per-effect planners that produce (text, scope) pairs for witness memories.

Each effect type maps to a small builder that inspects
``effect.effect_data`` and returns the memory text + KnowledgeScope,
or ``None`` when the effect has no meaningful payload (empty item
string, missing attribute, ...). Lives in its own module so
``timeline.effect_memory`` can stay within the WPS202 module-member
budget.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Callable

from knowledge.node import KnowledgeScope
from timeline.event import EventEffect

MemoryPlan = tuple[str, KnowledgeScope]
_Builder = Callable[[str, dict], "MemoryPlan | None"]


def _plan_item(name: str, effect_data: dict, verb: str) -> MemoryPlan | None:
    inventory_item = effect_data.get("item", "")
    if not inventory_item:
        return None
    return ("{0} {1} {2}".format(name, verb, inventory_item), KnowledgeScope.LOCAL)


def _plan_attribute(name: str, effect_data: dict) -> MemoryPlan | None:
    attr = effect_data.get("attribute", "")
    if not attr:
        return None
    return ("{0}'s {1} changed".format(name, attr), KnowledgeScope.LOCAL)


def _plan_status(name: str, effect_data: dict) -> MemoryPlan | None:
    new_status = effect_data.get("status", "")
    if not new_status:
        return None
    if new_status.strip().lower() == "dead":
        return ("{0} died".format(name), KnowledgeScope.CITY)
    return ("{0}'s condition changed to {1}".format(name, new_status), KnowledgeScope.LOCAL)


def _plan_move(name: str, effect_data: dict) -> MemoryPlan | None:
    destination = effect_data.get("to_location_id", "")
    if not destination:
        return ("{0} departed".format(name), KnowledgeScope.LOCAL)
    return ("{0} departed for {1}".format(name, destination), KnowledgeScope.LOCAL)


_DISPATCH: MappingProxyType[str, _Builder] = MappingProxyType(
    {
        "ADD_ITEM": lambda name, effect_data: _plan_item(name, effect_data, "acquired"),
        "REMOVE_ITEM": lambda name, effect_data: _plan_item(name, effect_data, "lost"),
        "CHANGE_ATTRIBUTE": _plan_attribute,
        "CHANGE_STATUS": _plan_status,
        "MOVE_NPC": _plan_move,
        "REMOVE_NPC": lambda name, _effect_data: (
            "{0} is no longer here".format(name),
            KnowledgeScope.LOCAL,
        ),
    },
)


def plan_memory(effect: EventEffect, npc_name: str) -> MemoryPlan | None:
    """Return the memory plan for ``effect``, or ``None`` to skip it.

    ``ADD_KNOWLEDGE`` is absent from ``_DISPATCH`` on purpose: its
    handler already writes its own graph node, and returning ``None``
    here keeps ``emit_memory`` from double-writing.
    """
    builder = _DISPATCH.get(effect.effect_type.upper())
    if builder is None:
        return None
    return builder(npc_name, effect.effect_data)
