"""Wait intent detection and forced-wait logic for incapacitated players."""

from __future__ import annotations

import re
import types

# ---------------------------------------------------------------------------
# Incapacitating states — force the player to WAIT
# ---------------------------------------------------------------------------

INCAPACITATING_STATES: frozenset[str] = frozenset((
    "unconscious",
    "stunned",
    "tied up",
    "frightened",
    "frozen",
))

# ---------------------------------------------------------------------------
# Wait keywords by language (matched at start of message, case-insensitive)
# ---------------------------------------------------------------------------

_WAIT_PATTERNS: types.MappingProxyType[str, tuple[re.Pattern, ...]] = types.MappingProxyType(
    {
        "English": (
            re.compile(r"^/wait\b", re.IGNORECASE),
            re.compile(r"^wait$", re.IGNORECASE),
            re.compile(r"^i wait$", re.IGNORECASE),
            re.compile(r"^pass$", re.IGNORECASE),
            re.compile(r"^pass turn$", re.IGNORECASE),
            re.compile(r"^skip turn$", re.IGNORECASE),
            re.compile(r"^do nothing$", re.IGNORECASE),
            re.compile(r"^i do nothing$", re.IGNORECASE),
            re.compile(r"^stand still$", re.IGNORECASE),
        ),
        "Russian": (
            re.compile(r"^/wait\b", re.IGNORECASE),
            re.compile(r"^жду$", re.IGNORECASE),
            re.compile(r"^пас$", re.IGNORECASE),
            re.compile(r"^ничего не делаю$", re.IGNORECASE),
            re.compile(r"^я жду$", re.IGNORECASE),
            re.compile(r"^пропускаю ход$", re.IGNORECASE),
            re.compile(r"^стою на месте$", re.IGNORECASE),
        ),
    }
)

# Fallback: /wait works in any language
_UNIVERSAL_PATTERN = re.compile(r"^/wait\b", re.IGNORECASE)


def detect_wait_intent(text: str, language: str = "English") -> bool:
    """Return True if *text* is a wait/skip-turn command.

    Checks language-specific keyword patterns at the start of the message.
    """
    stripped = text.strip()
    patterns = _WAIT_PATTERNS.get(language, ())
    for pattern in patterns:
        if pattern.search(stripped):
            return True
    if not patterns and _UNIVERSAL_PATTERN.search(stripped):
        return True
    return False


def is_incapacitated(physical_status: str) -> bool:
    """Return True if *physical_status* prevents the player from acting."""
    return physical_status.lower() in INCAPACITATING_STATES


def build_forced_wait_plan(reason: str) -> dict:
    """Build a routing plan dict for a forced WAIT action."""
    return {
        "action_type": "WAIT",
        "is_aggressive": False,
        "targets": [],
        "needs_clarification": False,
        "clarification_question": "",
        "delegate_to": ["narrator"],
        "time_cost_override": None,
        "wait_reason": reason,
    }
