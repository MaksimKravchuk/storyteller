"""Convert a tight Markdown subset into HTML.

The Narrator is instructed to emit only this subset:

- ``**bold**``           — emphasis on names, key items, critical events
- ``*italic*`` / ``_italic_`` — atmosphere, sounds, inner thoughts
- ```` `code` ````       — short written text the player reads
- Blank lines separate paragraphs

Anything else is treated as literal text. The converter is deterministic and
has no external dependencies.
"""

from __future__ import annotations

import re
from html import escape
from typing import Callable

_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(?!\s)([^*\n]+?)(?<!\s)\*(?!\*)")
_ITALIC_UNDER_RE = re.compile(r"(?<![A-Za-z0-9_])_(?!\s)([^_\n]+?)(?<!\s)_(?![A-Za-z0-9_])")
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")

_KIND_TEXT = "text"
_KIND_CODE = "code"


def to_html(md: str) -> str:
    """Render Markdown into standalone HTML with <p> paragraphs."""
    inline = _make_html_inline(bold="strong", italic="em", code="code")
    return _render_paragraphs(md, inline, joiner="\n", para_open="<p>", para_close="</p>")


def _render_paragraphs(
    md: str,
    inline: Callable[[str], str],
    joiner: str,
    para_open: str,
    para_close: str,
) -> str:
    """Split ``md`` into paragraphs, apply ``inline`` to each, rejoin."""
    if not md:
        return ""
    paragraphs = (para.strip() for para in _PARAGRAPH_SPLIT_RE.split(md.strip()))
    rendered = ["{0}{1}{2}".format(para_open, inline(para), para_close) for para in paragraphs if para]
    return joiner.join(rendered)


def _make_html_inline(*, bold: str, italic: str, code: str) -> Callable[[str], str]:
    """Return an inline renderer that wraps spans with the given HTML tags."""
    wrap_bold = _wrap_tag(bold)
    wrap_italic = _wrap_tag(italic)

    def render_inline(chunk: str) -> str:
        parts: list[str] = []
        for kind, body in _split_code_spans(chunk):
            escaped = escape(body, quote=False)
            if kind == _KIND_CODE:
                parts.append("<{0}>{1}</{0}>".format(code, escaped))
                continue
            escaped = _BOLD_RE.sub(wrap_bold, escaped)
            escaped = _ITALIC_STAR_RE.sub(wrap_italic, escaped)
            escaped = _ITALIC_UNDER_RE.sub(wrap_italic, escaped)
            parts.append(escaped)
        return "".join(parts)

    return render_inline


def _wrap_tag(tag: str) -> Callable[[re.Match[str]], str]:
    """Return a regex replacement function that wraps group 1 in ``<tag>``."""

    def replace(match: re.Match[str]) -> str:
        return "<{0}>{1}</{0}>".format(tag, match.group(1))

    return replace


def _split_code_spans(chunk: str) -> list[tuple[str, str]]:
    """Split ``chunk`` into ``(kind, body)`` segments around code spans."""
    segments: list[tuple[str, str]] = []
    cursor = 0
    for match in _CODE_SPAN_RE.finditer(chunk):
        segments.append((_KIND_TEXT, chunk[cursor : match.start()]))
        segments.append((_KIND_CODE, match.group(1)))
        cursor = match.end()
    segments.append((_KIND_TEXT, chunk[cursor:]))
    return segments
