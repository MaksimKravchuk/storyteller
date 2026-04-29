"""Shared Actor-related test helpers — mock builders and prompt renderers."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock

from cast.schemas.actor_reply import ActorReply
from prompts.actor_prompts import ACTOR_SYSTEM_ACTION, ACTOR_SYSTEM_DIALOGUE

# Default Actor-prompt rendering kwargs. Tests across test_actor_prompt.py,
# test_actor_revealed.py, and test_prompt_localization.py all need this shape;
# exposing it here keeps their defaults in lockstep so adding a new required
# var to ACTOR_SYSTEM_DIALOGUE only needs one test-side update.
BASE_ACTOR_PROMPT_VARS: types.MappingProxyType[str, str] = types.MappingProxyType(
    {
        "npc_name": "Guard",
        "npc_occupation": "city guard",
        "location_name": "forum",
        "npc_biography": "A loyal soldier.",
        "personality_traits": "brave, stern",
        "speech_style": "curt",
        "npc_appearance": "tall, armored",
        "npc_inventory": "spear, shield",
        "accessible_knowledge": "The forum closes at dusk.",
        "current_mood": "neutral",
        "physical_status": "healthy",
        "language": "English",
    },
)


def render_actor_system(
    mode: str = "dialogue",
    **overrides: str,
) -> str:
    """Render the Actor system prompt for the given output mode.

    ``mode`` is ``"dialogue"`` or ``"action"``.
    """
    prompt_vars = {**BASE_ACTOR_PROMPT_VARS, **overrides}
    template = ACTOR_SYSTEM_ACTION if mode == "action" else ACTOR_SYSTEM_DIALOGUE
    return template.render(**prompt_vars)


def actor_reply(text: str = "", revealed_names: list[str] | None = None) -> ActorReply:
    """Build an :class:`ActorReply` for tests."""
    return ActorReply(text=text, revealed_names=tuple(revealed_names or ()))


def make_mock_actor(text: str = "", revealed_names: list[str] | None = None) -> AsyncMock:
    """Create an Actor-shaped mock whose ``execute``/``act`` return an :class:`ActorReply`."""
    reply = actor_reply(text=text, revealed_names=revealed_names)
    mock = AsyncMock()
    mock.act = AsyncMock(return_value=reply)
    mock.execute = AsyncMock(return_value=reply)
    return mock
