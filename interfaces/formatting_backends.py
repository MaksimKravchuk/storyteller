"""Formatting backends for platform-specific text styling."""

from __future__ import annotations

from typing import Protocol


class FormattingBackend(Protocol):
    """Protocol for platform-specific text formatting."""

    def bold(self, text: str) -> str: ...

    def italic(self, text: str) -> str: ...

    def separator(self) -> str: ...

    def escape(self, text: str) -> str: ...


class TelegramHTMLBackend:
    """Telegram HTML parse_mode backend."""

    def bold(self, text: str) -> str:
        return f"<b>{text}</b>"

    def italic(self, text: str) -> str:
        return f"<i>{text}</i>"

    def separator(self) -> str:
        return "\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"

    def escape(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class PlainTextBackend:
    """Plain text backend — no formatting, passthrough."""

    def bold(self, text: str) -> str:
        return text

    def italic(self, text: str) -> str:
        return text

    def separator(self) -> str:
        return "\n---\n"

    def escape(self, text: str) -> str:
        return text
