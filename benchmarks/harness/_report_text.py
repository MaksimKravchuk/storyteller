"""Tiny text utilities shared by the report renderers.

Keeping these here lets the per-section renderers stay focused on layout
without each re-implementing quote truncation or pipe escaping.
"""

from __future__ import annotations

_ELLIPSIS = "…"
_PIPE = "|"
_ESCAPED_PIPE = r"\|"


def truncate_quote(text: str, limit: int) -> str:
    """Truncate a quote so it fits on a single report line."""
    if len(text) <= limit:
        return text
    return "{0}{1}".format(text[: limit - 1], _ELLIPSIS)


def escape_pipes(text: str) -> str:
    """Escape ``|`` so it does not break GFM table cells."""
    return text.replace(_PIPE, _ESCAPED_PIPE)
