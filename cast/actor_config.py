"""Module-level Actor helpers.

* ``ENVELOPE_MODE_DEFAULT`` — the ``ACTOR_ENVELOPE_MODE`` prod rollback
  lever, evaluated once at module import.
* ``format_past_memories`` — prompt-safe memory renderer.

Extracted from ``cast.actor`` so those concerns don't contribute to that
module's import or member count.
"""

from __future__ import annotations

import os

from knowledge.node import KnowledgeNode
from loguru import logger

_MEMORY_TEXT_MAX_CHARS = 200
_FALSY_ENV_VALUES = frozenset(("false", "0", "no", "off"))


def _read_envelope_mode_env() -> bool:
    """Parse ACTOR_ENVELOPE_MODE with pydantic-style falsy tolerance.

    Treats the documented production-rollback values ("false", "0", "no",
    "off" — case-insensitive) as disabling envelope mode. Any other value
    (including typos) keeps the default envelope path on.
    """
    return os.environ.get("ACTOR_ENVELOPE_MODE", "true").strip().lower() not in _FALSY_ENV_VALUES


def format_past_memories(memories: list[KnowledgeNode]) -> str:
    """Render a newline-joined bullet list of memory texts, truncated for prompt safety."""
    lines: list[str] = []
    for memory in memories:
        text = memory.text
        if len(text) > _MEMORY_TEXT_MAX_CHARS:
            text = "{0}...".format(text[: _MEMORY_TEXT_MAX_CHARS - 3])
        lines.append("- {0}".format(text))
    return "\n".join(lines)


# Prod rollback lever: set ACTOR_ENVELOPE_MODE=false/0/no/off in the deploy
# env to fall back to the legacy trailing-tag parser without a code
# redeploy. Evaluated once at module import — flipping the env var requires
# a process restart. Tests override via the ``envelope_mode`` constructor arg
# on ``cast.actor.Actor``.
ENVELOPE_MODE_DEFAULT: bool = _read_envelope_mode_env()
logger.info(
    "Actor envelope mode: {} (set ACTOR_ENVELOPE_MODE=false to roll back)",
    "ON" if ENVELOPE_MODE_DEFAULT else "OFF (legacy tag parser)",
)
