"""Schema for an Actor's dialogue return value.

Carries the spoken text alongside any ``[REVEALED: ...]`` tokens the
Actor emitted (see KER-29). Downstream, :class:`DialogueHandler`
resolves those tokens to NPC UUIDs and adds them to
``PlayerState.known_npcs`` so the Narrator can render ``Name
(Occupation)`` on subsequent turns instead of a generic descriptor.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ActorReply(BaseModel):
    """An Actor's dialogue response with extracted revelation tokens.

    ``text`` is the spoken line with all inline tags (``[MOOD:]``,
    ``[STATUS:]``, ``[REVEALED:]``) stripped. ``revealed_names`` carries
    the raw tokens the LLM supplied — ``"self"`` for the speaker, or
    another NPC's name verbatim. Resolution of tokens to UUIDs happens
    in :mod:`cast.director_dialogue` where the current scene's
    NPC list is available.
    """

    text: str
    revealed_names: list[str] = Field(default_factory=list)
