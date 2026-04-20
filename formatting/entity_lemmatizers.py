"""Language-aware lemmatization helpers for entity markup.

Russian uses pymorphy3 for full inflection coverage; English uses a tiny
suffix stemmer; anything else falls back to case-insensitive exact match
if pymorphy3 is unavailable.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from loguru import logger

from prompts.locales import Locale, resolve_locale

_ENGLISH_SUFFIXES = ("ing", "ed", "es", "s")
_MIN_STEM_LEN = 3

Lemmatizer = Callable[[str], str]


def pick_lemmatizer(language: str) -> Lemmatizer:
    """Return the lemmatization callable for ``language``.

    Falls back to a no-op lowercasing callable whenever the heavier
    backend is unavailable — that keeps callers free of try/except and
    gives the post-match its documented graceful-degradation behaviour.
    """
    locale = resolve_locale(language)
    if locale is Locale.RUSSIAN:
        return _russian_lemmatizer()
    return english_lemmatizer


def english_lemmatizer(token: str) -> str:
    """Tiny stemmer: lowercase, strip one common English suffix."""
    stem = token.lower()
    suffix = _first_strippable_suffix(stem)
    if suffix is None:
        return stem
    return stem[: -len(suffix)]


def exact_lowercase(token: str) -> str:
    """Fallback lemmatizer — used when pymorphy3 is unavailable."""
    return token.lower()


def _first_strippable_suffix(stem: str) -> str | None:
    """Return the first English suffix on ``stem`` that is safe to trim."""
    threshold = _MIN_STEM_LEN
    for suffix in _ENGLISH_SUFFIXES:
        if not stem.endswith(suffix):
            continue
        if len(stem) > len(suffix) + threshold:
            return suffix
    return None


class _PymorphyLemmatizer:
    """Callable wrapper around a pymorphy3 ``MorphAnalyzer``."""

    def __init__(self, analyzer) -> None:
        self._analyzer = analyzer

    def __call__(self, token: str) -> str:
        parses = self._analyzer.parse(token)
        if not parses:
            return token.lower()
        return parses[0].normal_form


@lru_cache(maxsize=1)
def _russian_lemmatizer() -> Lemmatizer:
    """Return a Russian lemmatizer backed by pymorphy3, with fallback."""
    try:
        import pymorphy3
    except ImportError:
        logger.warning(
            "pymorphy3 not installed — entity_markup will fall back to case-insensitive exact match",
        )
        return exact_lowercase
    return _PymorphyLemmatizer(pymorphy3.MorphAnalyzer())
