"""Transcript rendering helpers for the web interface.

Splits ``build_transcript`` and the per-role HTML renderers out of
``schemas.py`` so that module stays a pure model file (and stays under
wemake's ``WPS202 too many module members`` cap).
"""

from __future__ import annotations

from html import escape
from typing import Literal

from loguru import logger

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
    token_cache: dict[str, str] | None = None,
) -> str:
    """Render narrator markdown into the HTML subset used by the web UI.

    Wrap failures degrade to plain markdown HTML so already-paid-for
    narration is never dropped.
    """
    if not text:
        return ""
    html = markdown_render.to_html(text)
    if not visible_entities:
        return html
    try:
        return wrap_entities(html, visible_entities, language, token_cache)
    except Exception:
        logger.exception(
            "render_narrator_html: wrap_entities failed; returning plain HTML (language={0}, n_entities={1})",
            language,
            len(visible_entities),
        )
        return html


def render_player_html(text: str) -> str:
    """HTML-escape player input so it can be inserted via innerHTML safely."""
    return escape(text or "", quote=False)


def build_transcript(conversation_log: list[dict], language: str = _DEFAULT_LANGUAGE) -> list[TurnEntry]:
    """Convert ``GameState.conversation_log`` entries into flat TurnEntry pairs.

    Emits a player line followed by a narrator line per log entry.
    Narrator lines are re-wrapped with the ``visible_entities`` snapshot
    captured on the turn they were produced; legacy entries without that
    key fall back to plain markdown HTML.
    """
    transcript: list[TurnEntry] = []
    # Share one pymorphy3 cache across every narrator line so common
    # tokens ("дверь", "the") aren't re-lemmatised per-turn.
    token_cache: dict[str, str] = {}
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
                    html=render_narrator_html(
                        str(narrator_text),
                        _rehydrate_entities(entry.get("visible_entities")),
                        language,
                        token_cache,
                    ),
                ),
            )
    return transcript


def _rehydrate_entities(raw: object) -> list[VisibleEntity]:
    """Rebuild ``VisibleEntity`` instances from a persisted log entry.

    Tolerates missing, ``None``, or malformed payloads by skipping them
    — inline highlight for history is best-effort.
    """
    if not isinstance(raw, list):
        return []
    rehydrated: list[VisibleEntity] = []
    malformed = 0
    first_error: Exception | None = None
    for payload in raw:
        if not isinstance(payload, dict):
            malformed += 1
            continue
        try:
            rehydrated.append(VisibleEntity.model_validate(payload))
        except Exception as exc:
            malformed += 1
            if first_error is None:
                first_error = exc
    if malformed:
        # Log one representative traceback per batch so schema drift is
        # still investigable, without flooding Sentry per bad item.
        logger.opt(exception=first_error).warning(
            "build_transcript: skipped {0} malformed visible_entity payload(s)",
            malformed,
        )
    return rehydrated
