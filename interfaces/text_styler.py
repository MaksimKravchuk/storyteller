"""TextStyler — platform-aware text formatting for narrator output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from interfaces.formatting_backends import FormattingBackend


class SegmentType(Enum):
    PLAIN = auto()
    NPC_NAME = auto()
    DIALOGUE = auto()
    SCENE_HEADER = auto()
    SECTION_SEPARATOR = auto()


@dataclass
class StyledSegment:
    text: str
    segment_type: SegmentType


# Speech verbs used to identify NPC names adjacent to dialogue.
_SPEECH_VERBS = (
    r"says?|said|whispered?|shouted?|exclaimed?|muttered?|replied?"
    r"|growled?|called|cried|asked|answered|declared|murmured?"
    r"|hissed|snapped|yelled|screamed|bellowed|stammered"
)

# Pattern: Name + speech_verb + colon/comma + quoted text
# e.g.  Marcus says: "Halt!"  or  Guard whispered, "Come here."
_NAME_VERB_DIALOGUE = re.compile(
    rf"(?P<name>[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)"
    rf"\s+(?:{_SPEECH_VERBS})\s*[:,]?\s*"
    rf"(?P<dialogue>[\"«\u201c].+?[\"»\u201d])",
    re.DOTALL,
)

# Pattern: quoted dialogue + speech_verb + Name
# e.g.  "Welcome," said Marcus.
_DIALOGUE_VERB_NAME = re.compile(
    rf"(?P<dialogue>[\"«\u201c].+?[\"»\u201d])\s*,?\s*"
    rf"(?:{_SPEECH_VERBS})\s+"
    rf"(?P<name>[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)",
    re.DOTALL,
)

# Standalone quoted text (no NPC attribution)
_STANDALONE_QUOTE = re.compile(
    r"(?P<dialogue>[\"«\u201c].+?[\"»\u201d])",
    re.DOTALL,
)

# Section separators: ---, ***, ===, etc. on their own line
_SEPARATOR = re.compile(r"^[\-\*=]{3,}$", re.MULTILINE)

# Scene header: short first line (<=60 chars) followed by blank line + text
_SCENE_HEADER = re.compile(
    r"\A(?P<header>[^\n]{1,60})\n\n(?=\S)",
)


class TextStyler:
    """Parse narrator plain text and render with platform-specific formatting."""

    def __init__(self, backend: FormattingBackend) -> None:
        self._backend = backend

    def parse(self, text: str) -> list[StyledSegment]:
        """Identify semantic regions in plain text."""
        if not text:
            return []

        segments: list[StyledSegment] = []
        # Track which character ranges have been claimed by a pattern.
        claimed: list[tuple[int, int, StyledSegment]] = []

        # 1. Section separators
        for m in _SEPARATOR.finditer(text):
            claimed.append((
                m.start(),
                m.end(),
                StyledSegment(m.group(), SegmentType.SECTION_SEPARATOR),
            ))

        # 2. Scene header (only at the very start of text)
        header_match = _SCENE_HEADER.match(text)
        if header_match:
            claimed.append((
                header_match.start("header"),
                header_match.end("header"),
                StyledSegment(header_match.group("header"), SegmentType.SCENE_HEADER),
            ))

        # 3. Name + verb + dialogue  (e.g. Marcus says: "...")
        for m in _NAME_VERB_DIALOGUE.finditer(text):
            claimed.append((
                m.start("name"),
                m.end("name"),
                StyledSegment(m.group("name"), SegmentType.NPC_NAME),
            ))
            claimed.append((
                m.start("dialogue"),
                m.end("dialogue"),
                StyledSegment(m.group("dialogue"), SegmentType.DIALOGUE),
            ))

        # 4. Dialogue + verb + name  (e.g. "Hello," said Marcus)
        for m in _DIALOGUE_VERB_NAME.finditer(text):
            # Avoid duplicate dialogue claims
            d_start, d_end = m.start("dialogue"), m.end("dialogue")
            if not _overlaps(claimed, d_start, d_end):
                claimed.append((
                    d_start,
                    d_end,
                    StyledSegment(m.group("dialogue"), SegmentType.DIALOGUE),
                ))
            n_start, n_end = m.start("name"), m.end("name")
            if not _overlaps(claimed, n_start, n_end):
                claimed.append((
                    n_start,
                    n_end,
                    StyledSegment(m.group("name"), SegmentType.NPC_NAME),
                ))

        # 5. Standalone quoted text (dialogue without attribution)
        for m in _STANDALONE_QUOTE.finditer(text):
            d_start, d_end = m.start("dialogue"), m.end("dialogue")
            if not _overlaps(claimed, d_start, d_end):
                claimed.append((
                    d_start,
                    d_end,
                    StyledSegment(m.group("dialogue"), SegmentType.DIALOGUE),
                ))

        # Sort claimed by start position
        claimed.sort(key=lambda c: c[0])

        # Fill gaps with PLAIN segments
        pos = 0
        for start, end, segment in claimed:
            if start > pos:
                plain_text = text[pos:start]
                if plain_text:
                    segments.append(StyledSegment(plain_text, SegmentType.PLAIN))
            segments.append(segment)
            pos = end

        # Trailing plain text
        if pos < len(text):
            trailing = text[pos:]
            if trailing:
                segments.append(StyledSegment(trailing, SegmentType.PLAIN))

        # If nothing was claimed, return whole text as PLAIN
        if not segments:
            segments.append(StyledSegment(text, SegmentType.PLAIN))

        return segments

    def format(self, text: str) -> str:
        """Parse and render text with the configured backend."""
        if not text:
            return ""

        segments = self.parse(text)
        parts: list[str] = []

        for segment in segments:
            if segment.segment_type == SegmentType.PLAIN:
                parts.append(self._backend.escape(segment.text))
            elif segment.segment_type == SegmentType.NPC_NAME:
                parts.append(self._backend.bold(self._backend.escape(segment.text)))
            elif segment.segment_type == SegmentType.DIALOGUE:
                parts.append(self._backend.italic(self._backend.escape(segment.text)))
            elif segment.segment_type == SegmentType.SCENE_HEADER:
                parts.append(self._backend.bold(self._backend.escape(segment.text)))
            elif segment.segment_type == SegmentType.SECTION_SEPARATOR:
                parts.append(self._backend.separator())

        return "".join(parts)


def _overlaps(
    claimed: list[tuple[int, int, StyledSegment]],
    start: int,
    end: int,
) -> bool:
    """Check if a range overlaps with any already-claimed range."""
    for c_start, c_end, _ in claimed:
        if start < c_end and end > c_start:
            return True
    return False
