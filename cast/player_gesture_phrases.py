"""Locale-aware action phrases for structured player gestures.

When a player taps an in-prose entity or a map place instead of typing,
the web client sends a language-neutral gesture ``{intent, entity_kind,
entity_id}`` rather than a phrase. The server resolves the target's
player-visible name and composes the action *in the session language*
here, so non-English play is never broken by a hardcoded English verb
(the hard constraint from ADR-0006 / ADR-0010).

:class:`GesturePhrases` bundles one format string per intent for a
single locale; ``{0}`` is the target-name slot. :func:`get_gesture_phrases`
returns the bundle for the player's chosen language, falling back to
English for unsupported locales — mirroring :mod:`cast.narrator_labels`.

v1 limitation: the Russian phrases inject the target name in its
nominative form without pymorphy3 declension (e.g. "поговорить с
стражник" rather than the declined "со стражником"). This still
satisfies the hard constraint — Russian output, no English verb — and
matches the same imperfection the ``narrator_labels`` precedent accepts.
"""

from __future__ import annotations

from dataclasses import dataclass

from prompts.locales import Locale, make_locale_lookup


@dataclass(frozen=True)
class GesturePhrases:
    """Action phrases for one locale, keyed by gesture intent.

    Every field is a *format string* embedding a single ``{0}``
    placeholder for the resolved, player-visible target name.
    """

    examine: str  # "examine {0}"
    talk: str  # "talk to {0}"
    move: str  # "go to {0}"


_ENGLISH = GesturePhrases(
    examine="examine {0}",
    talk="talk to {0}",
    move="go to {0}",
)


_RUSSIAN = GesturePhrases(
    examine="осмотреть {0}",
    talk="поговорить с {0}",
    move="пойти к {0}",
)


get_gesture_phrases = make_locale_lookup(
    {
        Locale.ENGLISH: _ENGLISH,
        Locale.RUSSIAN: _RUSSIAN,
    }
)
