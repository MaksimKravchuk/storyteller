"""Schema for an Actor's dialogue return value."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ActorReply(BaseModel):
    """An Actor's dialogue response with extracted revelation tokens.

    ``text`` is the spoken line with all inline tags (``[MOOD:]``,
    ``[STATUS:]``, ``[REVEALED:]``) stripped. ``revealed_names`` carries
    the raw tokens the LLM supplied — ``"self"`` for the speaker, or
    another NPC's name verbatim. Token → UUID resolution is scoped to
    the current scene to prevent cross-scene same-name leaks.
    """

    text: str
    revealed_names: list[str] = Field(default_factory=list)
