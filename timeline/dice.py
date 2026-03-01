"""DnD-style dice roll and skill check system."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum


class CheckType(Enum):
    """Categories of skill checks."""

    COMBAT = "combat"
    PERSUASION = "persuasion"
    STEALTH = "stealth"
    PERCEPTION = "perception"
    CRAFTING = "crafting"
    KNOWLEDGE = "knowledge"
    ATHLETICS = "athletics"
    SURVIVAL = "survival"


class CheckResult(Enum):
    """Outcome of a dice check."""

    CRITICAL_FAIL = "critical_fail"  # Rolled 1
    FAIL = "fail"  # Total < DC
    SUCCESS = "success"  # Total >= DC
    CRITICAL_SUCCESS = "critical_success"  # Rolled 20


@dataclass(frozen=True)
class DiceOutcome:
    """Full result of a skill check."""

    check_type: CheckType
    raw_roll: int  # The d20 result
    modifier: int  # Attribute-derived modifier
    total: int  # raw_roll + modifier
    difficulty_class: int  # DC that was checked against
    result: CheckResult
    description: str = ""  # Optional narrative description

    @property
    def succeeded(self) -> bool:
        return self.result in (CheckResult.SUCCESS, CheckResult.CRITICAL_SUCCESS)


# Mapping from CheckType to the NPC attribute key used as modifier source.
# The attribute value (0-10) is converted to a modifier via (value - 5),
# giving a range of -5 to +5.
CHECK_ATTRIBUTE_MAP: dict[CheckType, str] = {
    CheckType.COMBAT: "combat",
    CheckType.PERSUASION: "persuasion",
    CheckType.STEALTH: "stealth",
    CheckType.PERCEPTION: "perception",
    CheckType.CRAFTING: "crafting",
    CheckType.KNOWLEDGE: "education",
    CheckType.ATHLETICS: "athletics",
    CheckType.SURVIVAL: "survival",
}

# Standard difficulty classes
DC_TRIVIAL = 5
DC_EASY = 8
DC_MODERATE = 10
DC_HARD = 15
DC_VERY_HARD = 18
DC_NEARLY_IMPOSSIBLE = 22


def attribute_to_modifier(attribute_value: int) -> int:
    """Convert a 0-10 attribute to a -5 to +5 modifier."""
    return attribute_value - 5


def roll_d20() -> int:
    """Roll a single d20."""
    return random.randint(1, 20)


def skill_check(
    check_type: CheckType,
    attribute_value: int,
    difficulty_class: int = DC_MODERATE,
    *,
    advantage: bool = False,
    disadvantage: bool = False,
) -> DiceOutcome:
    """Perform a DnD-style skill check.

    Args:
        check_type: The type of check being performed.
        attribute_value: The NPC's attribute value (0-10 scale).
        difficulty_class: The DC to beat (default 10, "moderate").
        advantage: Roll 2d20, take higher.
        disadvantage: Roll 2d20, take lower.

    Returns:
        A DiceOutcome with full details.
    """
    modifier = attribute_to_modifier(attribute_value)

    if advantage and not disadvantage:
        raw_roll = max(roll_d20(), roll_d20())
    elif disadvantage and not advantage:
        raw_roll = min(roll_d20(), roll_d20())
    else:
        raw_roll = roll_d20()

    total = raw_roll + modifier

    if raw_roll == 1:
        result = CheckResult.CRITICAL_FAIL
    elif raw_roll == 20:
        result = CheckResult.CRITICAL_SUCCESS
    elif total >= difficulty_class:
        result = CheckResult.SUCCESS
    else:
        result = CheckResult.FAIL

    return DiceOutcome(
        check_type=check_type,
        raw_roll=raw_roll,
        modifier=modifier,
        total=total,
        difficulty_class=difficulty_class,
        result=result,
    )


def npc_skill_check(
    npc_attributes: dict[str, int],
    check_type: CheckType,
    difficulty_class: int = DC_MODERATE,
    **kwargs,
) -> DiceOutcome:
    """Perform a skill check using an NPC's attributes dict."""
    attr_key = CHECK_ATTRIBUTE_MAP.get(check_type, "")
    attr_value = npc_attributes.get(attr_key, 5)  # Default 5 = modifier 0
    return skill_check(check_type, attr_value, difficulty_class, **kwargs)
