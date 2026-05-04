"""Input DTO for player character creation at game start.

Distinct from :class:`models.game_state.PlayerState` so request bodies
cannot set runtime fields (``location_id``, ``known_npcs``,
``learned_facts``, etc.). Only carries the fields the player provides
during onboarding.
"""

from __future__ import annotations

from pydantic import BaseModel


class PlayerCharacterInput(BaseModel):
    """Player-provided character info collected during onboarding.

    All fields are optional. ``name`` defaults to an empty string —
    NPCs build their own memory of the player from appearance and
    behaviour, so the player can stay anonymous.

    ``origin_era`` is the deterministic anchor the anachronism
    classifier consumes when judging whether a player action is out
    of period for the in-game setting. Inferring it from the inventory
    text fails when the player carries era-neutral items (a knife in
    ancient Rome looks the same as a knife in 21st-century Earth), so
    we collect it explicitly. An empty string disables the classifier
    — same-era runs pay no LLM cost.
    """

    name: str = ""
    appearance: str = ""
    inventory: list[str] = []
    origin_era: str = ""
