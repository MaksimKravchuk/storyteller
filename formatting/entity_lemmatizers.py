"""Language-aware lemmatization helpers for entity markup.

Russian uses pymorphy3 for full inflection coverage; other languages fall back
to case-insensitive exact match. If pymorphy3 is missing or its dictionary
fails to load — which should not happen in production since pymorphy3 is a
required dependency — the Russian path degrades to case-insensitive exact match
and is logged loudly so operators can trace the break.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

from loguru import logger

from prompts.locales import Locale, resolve_locale

Lemmatizer = Callable[[str], str]
NounTest = Callable[[str], bool]


def pick_lemmatizer(language: str) -> Lemmatizer:
    """Return the lemmatization callable for ``language``."""
    locale = resolve_locale(language)
    if locale is Locale.RUSSIAN:
        return _russian_lemmatizer()
    return exact_lowercase


def pick_noun_test(language: str) -> NounTest | None:
    """Return a "is this token a noun?" check for ``language``, if one exists.

    Only Russian has a part-of-speech tagger (pymorphy3); other languages
    return ``None`` and callers fall back to a word-order heuristic.
    """
    if resolve_locale(language) is not Locale.RUSSIAN:
        return None
    analyzer = _russian_analyzer()
    if analyzer is None:
        return None
    return _PymorphyNounTest(analyzer)


def exact_lowercase(token: str) -> str:
    return token.lower()


class _PymorphyLemmatizer:
    """Callable wrapper around a pymorphy3 ``MorphAnalyzer``."""

    def __init__(self, analyzer) -> None:
        self._analyzer = analyzer

    def __call__(self, token: str) -> str:
        parses = self._analyzer.parse(token)
        if not parses:
            return token.lower()
        return parses[0].normal_form


class _PymorphyNounTest:
    """Callable reporting whether pymorphy3's best parse of a token is a noun."""

    def __init__(self, analyzer) -> None:
        self._analyzer = analyzer

    def __call__(self, token: str) -> bool:
        parses = self._analyzer.parse(token)
        return bool(parses) and parses[0].tag.POS == "NOUN"


@lru_cache(maxsize=1)
def _russian_lemmatizer() -> Lemmatizer:
    """Return a Russian lemmatizer backed by pymorphy3, with loud fallback.

    pymorphy3 is a required dependency of this project (see
    ``pyproject.toml``), so an ``ImportError`` or ``MorphAnalyzer``
    construction failure here indicates a broken install, not an
    optional-dep miss. Log at ``error`` level so Sentry picks it up,
    and return the case-insensitive fallback so the render path
    survives — Russian entity matching will silently miss inflected
    forms until the install is fixed.
    """
    analyzer = _russian_analyzer()
    if analyzer is None:
        return exact_lowercase
    return _PymorphyLemmatizer(analyzer)


@lru_cache(maxsize=1)
def _russian_analyzer() -> Any | None:
    """Return the shared pymorphy3 ``MorphAnalyzer``, or ``None`` if it can't load."""
    try:
        import pymorphy3
    except ImportError:
        logger.error(
            "pymorphy3 not importable — Russian entity_markup degrading to exact-lowercase. "
            "Required dependency missing; check the Python environment.",
        )
        return None
    try:
        return pymorphy3.MorphAnalyzer()
    except Exception:
        logger.exception(
            "pymorphy3.MorphAnalyzer() failed — Russian entity_markup degrading to exact-lowercase.",
        )
        return None
