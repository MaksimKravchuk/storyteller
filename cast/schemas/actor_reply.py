"""Schema for an Actor's dialogue return value."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ActorReply(BaseModel):
    """An Actor's dialogue response with extracted revelation tokens.

    ``text`` is the spoken line with all inline tags (``[MOOD:]``,
    ``[STATUS:]``, ``[REVEALED:]``) stripped. ``revealed_names`` carries
    the raw tokens the LLM supplied — ``"self"`` for the speaker, or
    another NPC's name verbatim. Token → UUID resolution is scoped to
    the current scene to prevent cross-scene same-name leaks.

    Frozen + ``tuple`` fields signal that the reply is read-only after
    construction; consumers only iterate ``revealed_names`` into
    ``set.update``, so immutability is a cheap footgun-remover.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    revealed_names: tuple[str, ...] = ()
