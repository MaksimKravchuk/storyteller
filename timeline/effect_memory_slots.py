"""Slot derivation for effect-driven witness memories.

Maps each ``EventEffect.effect_type`` to a structured-slot builder.
Lives in its own module so the verb table and per-effect dispatch can
grow without crowding :mod:`timeline.effect_memory`.
"""

from __future__ import annotations

from types import MappingProxyType

from knowledge.memory_slots import EMPTY_SLOTS, MemorySlots
from timeline.event import EventEffect

_ETYPE_ADD_ITEM = "ADD_ITEM"
_ETYPE_REMOVE_ITEM = "REMOVE_ITEM"
_ETYPE_CHANGE_ATTRIBUTE = "CHANGE_ATTRIBUTE"
_ETYPE_CHANGE_STATUS = "CHANGE_STATUS"
_ETYPE_MOVE_NPC = "MOVE_NPC"
_ETYPE_REMOVE_NPC = "REMOVE_NPC"

_DATA_ITEM = "item"
_DATA_STATUS = "status"
_DATA_ATTRIBUTE = "attribute"
_DATA_TO_LOCATION = "to_location_id"
_STATUS_DEAD = "dead"

_ACTION_BY_EFFECT: MappingProxyType[str, str] = MappingProxyType(
    {
        _ETYPE_ADD_ITEM: "acquired",
        _ETYPE_REMOVE_ITEM: "lost",
        _ETYPE_CHANGE_ATTRIBUTE: "changed_attribute",
        _ETYPE_CHANGE_STATUS: "changed_status",
        _ETYPE_MOVE_NPC: "departed",
        _ETYPE_REMOVE_NPC: "left_scene",
    },
)


def _slots_for_status(name: str, action: str | None, edata: dict) -> MemorySlots:
    status = edata.get(_DATA_STATUS, "").strip().lower()
    return MemorySlots(
        subject=name,
        action="died" if status == _STATUS_DEAD else action,
        outcome=status or None,
    )


def _slots_for_item(name: str, action: str | None, edata: dict) -> MemorySlots:
    return MemorySlots(subject=name, action=action, object=edata.get(_DATA_ITEM) or None)


def _slots_for_move(name: str, action: str | None, edata: dict) -> MemorySlots:
    return MemorySlots(subject=name, action=action, outcome=edata.get(_DATA_TO_LOCATION) or None)


def _slots_for_attribute(name: str, action: str | None, edata: dict) -> MemorySlots:
    return MemorySlots(subject=name, action=action, object=edata.get(_DATA_ATTRIBUTE) or None)


def _slots_for_remove(name: str, action: str | None, _edata: dict) -> MemorySlots:
    return MemorySlots(subject=name, action=action)


_BUILDER_BY_ETYPE = MappingProxyType(
    {
        _ETYPE_ADD_ITEM: _slots_for_item,
        _ETYPE_REMOVE_ITEM: _slots_for_item,
        _ETYPE_CHANGE_STATUS: _slots_for_status,
        _ETYPE_MOVE_NPC: _slots_for_move,
        _ETYPE_CHANGE_ATTRIBUTE: _slots_for_attribute,
        _ETYPE_REMOVE_NPC: _slots_for_remove,
    },
)


def slots_for_effect(effect: EventEffect, name: str) -> MemorySlots:
    """Derive structured slots from one ``EventEffect``.

    Returns :data:`~knowledge.memory_slots.EMPTY_SLOTS` for effect types
    we have no slot mapping for; the free-text summary on the
    ``KnowledgeNode`` remains the primary surface either way.
    """
    etype = effect.effect_type.upper()
    builder = _BUILDER_BY_ETYPE.get(etype)
    if builder is None:
        return EMPTY_SLOTS
    return builder(name, _ACTION_BY_EFFECT.get(etype), effect.effect_data)
