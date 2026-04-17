"""Shared constants for the cast package."""

# Actions that increment the turn counter.
TURN_COUNTING_ACTIONS: frozenset[str] = frozenset(("EXPLORE", "MOVE", "INTERACT", "TALK", "SLEEP", "WAIT"))

# Actions that trigger a scene rebuild (location change or time-of-day shift).
# EXPLORE / LOOK does not belong here — the player hasn't moved and time
# hasn't flipped, so re-running SceneBuilder would orphan any pre-seeded or
# previously-generated NPCs in the scene (KER-33).
SCENE_CHANGING_ACTIONS: frozenset[str] = frozenset(("MOVE", "SLEEP"))
