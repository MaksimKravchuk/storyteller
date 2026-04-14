"""Schema for the Dramaturge LLM JSON response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DramaturgeResponse(BaseModel):
    """Typed view of the Dramaturge review response.

    The prompt asks the LLM to copy ``corrected_narration`` through
    verbatim when nothing contradicts — so in the happy path the field
    carries a full narration string. ``Dramaturge.act`` treats an empty
    string as a bug signal and falls back to the raw narration, logging
    a warning.

    ``contradictions`` carries short human-readable descriptions of each
    fix applied, strictly for logging and tests. The player never sees
    this list.

    ``unknown_entities`` carries bare Wikipedia titles for any person,
    place, or item the LLM flagged as missing from the historical canon.
    They are fed to ``DataMiner.ensure_fact`` so future turns have the
    fact on hand. Escalation is best-effort — failures never break the
    current turn.
    """

    corrected_narration: str = ""
    contradictions: list[str] = Field(default_factory=list)
    unknown_entities: list[str] = Field(default_factory=list)
