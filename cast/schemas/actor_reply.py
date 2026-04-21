"""Schema for an Actor's dialogue return value."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

_NARRATION_MAX = 4000
_REVEALED_NAMES_MAX = 8
_NAME_TOKEN_MAX = 120

_NarrationStr = Annotated[str, Field(min_length=1, max_length=_NARRATION_MAX)]
_NameToken = Annotated[str, Field(min_length=1, max_length=_NAME_TOKEN_MAX)]
_RevealedNames = Annotated[list[_NameToken], Field(max_length=_REVEALED_NAMES_MAX)]


class ActorEnvelope(BaseModel):
    """On-wire shape returned by the Actor LLM.

    Parses the four-field JSON object the Actor system prompt asks the
    LLM to emit.  ``narration`` is the prose/dialogue text the player
    sees.  ``mood`` and ``status`` are optional NPC-state deltas the
    LLM signals per turn (``None`` when unchanged).  ``revealed_names``
    lists name tokens the NPC uttered (``"self"`` for the speaker, or
    another NPC's name verbatim) for scene-scoped introduction tracking.

    Invariants enforced at parse time:

    * ``narration`` is non-empty and length-capped — a blank narration
      would ship a silent NPC turn to the player; an extreme length is
      almost certainly an LLM format break, not legitimate content.
    * ``revealed_names`` is size-capped and each token is non-empty —
      a hallucinated 100-name list would flood the scene introduction
      pipeline.
    * Extra fields are forbidden so a schema-drifted LLM (e.g. emitting
      ``"emotion"`` instead of ``"mood"``) fails loudly into the retry
      path rather than silently producing ``mood=None``.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    narration: _NarrationStr
    mood: str | None = None
    status: str | None = None
    revealed_names: _RevealedNames = Field(default_factory=list)


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
