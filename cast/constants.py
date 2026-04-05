"""Shared constants for the cast package."""

# Actions that increment the turn counter.
TURN_COUNTING_ACTIONS: frozenset[str] = frozenset(("EXPLORE", "MOVE", "INTERACT", "TALK", "SLEEP", "WAIT"))

# Actions that trigger a scene rebuild (new location, time-of-day shift, etc.).
SCENE_CHANGING_ACTIONS: frozenset[str] = frozenset(("EXPLORE", "MOVE", "SLEEP"))
