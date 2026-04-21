"""Schema for an Actor's dialogue return value."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ActorEnvelope(BaseModel):
    """On-wire shape returned by the Actor LLM via strict JSON schema.

    The Actor prompt instructs the LLM to emit a JSON object; this model
    validates and parses it.  ``narration`` is the prose/dialogue text.
    ``mood``, ``status``, and ``revealed_names`` carry the metadata that
    the old tag-parsing path extracted via regex.
    """

    narration: str
    mood: str | None = None
    status: str | None = None
    revealed_names: list[str] = []


class ActorReply(BaseModel):
    """An Actor's dialogue response — public return type of ``Actor.act``.

    ``text`` is the spoken line. ``revealed_names`` carries the raw
    tokens the LLM supplied — ``"self"`` for the speaker, or another
    NPC's name verbatim. Token → UUID resolution is scoped to the
    current scene to prevent cross-scene same-name leaks.

    Frozen + ``tuple`` fields signal that the reply is read-only after
    construction; consumers only iterate ``revealed_names`` into
    ``set.update``, so immutability is a cheap footgun-remover.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    revealed_names: tuple[str, ...] = ()
