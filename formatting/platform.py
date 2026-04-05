"""Client platform identifiers used to pick output markup syntax."""

from __future__ import annotations

from enum import Enum


class ClientPlatform(str, Enum):
    """Identifies which markup syntax to render Narrator output into."""

    PLAIN = "plain"
    TELEGRAM_HTML = "telegram_html"
    HTML = "html"
