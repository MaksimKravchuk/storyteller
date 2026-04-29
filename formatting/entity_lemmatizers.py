"""Language-aware lemmatization helpers for entity markup.

Russian uses pymorphy3 for full inflection coverage; other languages fall back
to case-insensitive exact match. If pymorphy3 is missing or its dictionary
fails to load — which should not happen in production since pymorphy3 is a
required dependency — the Russian path degrades to case-insensitive exact match
and is logged loudly so operators can trace the break.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from loguru import logger

from prompts.locales import Locale, resolve_locale

Lemmatizer = Callable[[str], str]


def pick_lemmatizer(language: str) -> Lemmatizer:
    """Return the lemmatization callable for ``language``."""
    locale = resolve_locale(language)
    if locale is Locale.RUSSIAN:
        return _russian_lemmatizer()
    return exact_lowercase


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
    try:
        import pymorphy3
    except ImportError:
        logger.error(
            "pymorphy3 not importable — Russian entity_markup degrading to exact-lowercase. "
            "Required dependency missing; check the Python environment.",
        )
        return exact_lowercase
    try:
        analyzer = pymorphy3.MorphAnalyzer()
    except Exception:
        logger.exception(
            "pymorphy3.MorphAnalyzer() failed — Russian entity_markup degrading to exact-lowercase.",
        )
        return exact_lowercase
    return _PymorphyLemmatizer(analyzer)
