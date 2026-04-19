"""Transcript rendering helpers for the web interface.

Splits ``build_transcript`` and the per-role HTML renderers out of
``schemas.py`` so that module stays a pure model file (and stays under
wemake's ``WPS202 too many module members`` cap).
"""

from __future__ import annotations

from html import escape
from typing import Literal

from formatting import markdown_render
from formatting.entity_markup import wrap_entities
from interfaces.web.schemas import TurnEntry
from models.visible_entity import VisibleEntity

_ROLE_PLAYER: Literal["player"] = "player"
_ROLE_NARRATOR: Literal["narrator"] = "narrator"
_DEFAULT_LANGUAGE = "English"


def render_narrator_html(
    text: str,
    visible_entities: list[VisibleEntity] | None = None,
    language: str = _DEFAULT_LANGUAGE,
) -> str:
    """Render narrator markdown into the HTML subset used by the web UI.

    When ``visible_entities`` is provided, the rendered HTML is also
    post-processed by :func:`formatting.entity_markup.wrap_entities`
    so entity mentions (NPC names, POI aliases, tracked items) are
    wrapped in clickable spans carrying the entity kind and id.
    """
    if not text:
        return ""
    html = markdown_render.to_html(text)
    if not visible_entities:
        return html
    return wrap_entities(html, visible_entities, language)


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
