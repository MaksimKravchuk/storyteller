"""WorldState ↔ JSONB dict converters.

The whole living-world state lives as a single JSONB blob on the
``game_states`` row. Pydantic handles both directions: ``model_dump``
serialises and ``model_validate`` enforces the ``Literal`` constraints
on thread category/status. Legacy rows where ``world_state`` is
``NULL`` deserialise to a fresh empty :class:`WorldState`.
"""

from __future__ import annotations

from typing import Any

from models.world_state import WorldState


def world_state_to_dict(state: WorldState) -> dict[str, Any]:
    """Serialise a :class:`WorldState` into a JSON-ready dict."""
    return state.model_dump(mode="json")


def dict_to_world_state(payload: dict[str, Any] | None) -> WorldState:
    """Rehydrate a :class:`WorldState` from a JSONB payload."""
    if not payload:
        return WorldState()
    return WorldState.model_validate(payload)
