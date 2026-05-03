"""Structured slot bundle attached to memory nodes.

Memory nodes carry an optional ``subject``/``object``/``action``/``outcome``
quadruple alongside their free-text summary so downstream dedup,
querying, and contradiction detection can match on structured metadata
instead of re-parsing prose. Empty slots default to ``None`` so the
bundle remains a no-op for historical Wikipedia facts and other sites
without a clear actor.

The bundle is threaded through :class:`knowledge.memory.MemoryEvent`
(``MemoryEvent.slots``) and through ``summarize_interactions_batch``
pairs as the third tuple element.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemorySlots:
    """Structured metadata attached to a memory node.

    All four fields default to ``None`` so callers can populate only the
    slots they have. The free-text summary on the ``KnowledgeNode``
    remains the primary display surface.
    """

    subject: str | None = None
    object: str | None = None
    action: str | None = None
    outcome: str | None = None


EMPTY_SLOTS = MemorySlots()


def slot_kwargs(slots: MemorySlots) -> dict:
    """Spread ``slots`` into ``KnowledgeNode`` kwargs.

    The return type is intentionally untyped: callers spread it via
    ``**`` into ``KnowledgeNode(...)``, and a strict ``dict[str, str |
    None]`` would defeat mypy's per-kwarg type narrowing on the call.
    """
    return {
        "subject": slots.subject,
        "object": slots.object,
        "action": slots.action,
        "outcome": slots.outcome,
    }
