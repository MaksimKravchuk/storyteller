"""Wait intent detection and forced-wait logic for incapacitated players."""

from __future__ import annotations

import re
import types

from cast.schemas.action_plan import WaitPlan

# ---------------------------------------------------------------------------
# Incapacitating states — force the player to WAIT
# ---------------------------------------------------------------------------

INCAPACITATING_STATES: frozenset[str] = frozenset(
    (
        "unconscious",
        "stunned",
        "tied up",
        "frightened",
        "frozen",
    )
)

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
    return (physical_status or "").lower() in INCAPACITATING_STATES


def build_forced_wait_plan(reason: str) -> WaitPlan:
    """Build a typed WaitPlan for a forced WAIT action.

    Used when the player is incapacitated or typed a wait keyword, so
    no LLM round-trip is needed. The shape mirrors what the tool-call
    path would produce for a voluntary WAIT.
    """
    return WaitPlan(
        intent="wait ({0})".format(reason),
        delegate_to=["narrator"],
        time_cost_override=None,
        wait_reason=reason,
    )
