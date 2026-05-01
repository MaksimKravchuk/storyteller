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
    """

    name: str = ""
    appearance: str = ""
    inventory: list[str] = []
