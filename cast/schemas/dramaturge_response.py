"""Schema for the Dramaturge LLM JSON response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DramaturgeResponse(BaseModel):
    """Typed view of the Dramaturge review response.

    ``corrected_narration`` holds the full Narrator passage after the
    Dramaturge has rewritten any sentences that contradict historical
    canon or prior in-scene dialogue. When nothing was wrong the LLM
    is instructed to copy the narration through verbatim, so the field
    always carries a complete narration string and never an empty diff.

    ``contradictions`` carries short descriptions of each fix applied,
    strictly for logging and tests — the player never sees this list.
    """

    corrected_narration: str = ""
    contradictions: list[str] = Field(default_factory=list)
