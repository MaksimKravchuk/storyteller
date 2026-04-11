"""Transcript rendering helpers for the web interface.

Splits ``build_transcript`` and the per-role HTML renderers out of
``schemas.py`` so that module stays a pure model file (and stays under
wemake's ``WPS202 too many module members`` cap).
"""

from __future__ import annotations

from html import escape
from typing import Literal

from formatting import markdown_render
from interfaces.web.schemas import TurnEntry

_ROLE_PLAYER: Literal["player"] = "player"
_ROLE_NARRATOR: Literal["narrator"] = "narrator"


def render_narrator_html(text: str) -> str:
    """Render narrator markdown into the HTML subset used by the web UI."""
    return markdown_render.to_html(text) if text else ""


def render_player_html(text: str) -> str:
    """HTML-escape player input so it can be inserted via innerHTML safely."""
    return escape(text or "", quote=False)


def build_transcript(conversation_log: list[dict]) -> list[TurnEntry]:
    """Convert ``GameState.conversation_log`` entries into flat TurnEntry pairs.

    Each log entry has shape ``{player_action, response, turn, ...}``; we emit
    a player line followed by a narrator line so the client can render a chat
    log without knowing the internal schema. Each entry carries both raw
    ``text`` and pre-rendered ``html``.
    """
    transcript: list[TurnEntry] = []
    for entry in conversation_log:
        player_text = entry.get("player_action")
        if player_text:
            transcript.append(
                TurnEntry(
                    role=_ROLE_PLAYER,
                    text=str(player_text),
                    html=render_player_html(str(player_text)),
                ),
            )
        narrator_text = entry.get("response")
        if narrator_text:
            transcript.append(
                TurnEntry(
                    role=_ROLE_NARRATOR,
                    text=str(narrator_text),
                    html=render_narrator_html(str(narrator_text)),
                ),
            )
    return transcript
