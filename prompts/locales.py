"""Prompt locale registry.

Each player session carries a ``language`` string (``"English"``,
``"Russian"``, etc.). Agents that render prompts need two things from
that string:

1. A canonical :class:`Locale` identifier so they can look up the
   matching prompt catalog (the Narrator system prompt in Russian vs.
   English, etc.).
2. A human-readable label to inject into the prompt itself — e.g. the
   ``{language}`` placeholder in the Narrator system prompt, which
   instructs the LLM to write its output in that tongue.

:func:`resolve_locale` handles (1) by mapping every reasonable alias
("english", "en", "русский", ...) onto the enum and falling back to
:data:`DEFAULT_LOCALE` when the value is unrecognised. The raw label
for (2) is whatever the caller passed in.
"""

from __future__ import annotations

import enum
import types
from typing import Generic, TypeVar


class Locale(str, enum.Enum):
    """Supported prompt locales.

    The string value is the canonical lowercase name so that
    ``Locale("english")`` works and so that the enum is JSON-friendly
    if we ever need to persist it.
    """

    ENGLISH = "english"
    RUSSIAN = "russian"


DEFAULT_LOCALE: Locale = Locale.ENGLISH

_LOCALE_ALIASES: types.MappingProxyType[str, Locale] = types.MappingProxyType(
    {
        # English
        "english": Locale.ENGLISH,
        "en": Locale.ENGLISH,
        "eng": Locale.ENGLISH,
        # Russian
        "russian": Locale.RUSSIAN,
        "ru": Locale.RUSSIAN,
        "rus": Locale.RUSSIAN,
        "русский": Locale.RUSSIAN,
        "русский язык": Locale.RUSSIAN,
    }
)


_LT = TypeVar("_LT")


class _LocaleLookup(Generic[_LT]):
    """Callable mapping a language string to its per-locale catalog entry."""

    def __init__(self, catalog: dict[Locale, _LT]) -> None:
        self._catalog: types.MappingProxyType[Locale, _LT] = types.MappingProxyType(catalog)

    def __call__(self, language: str | None) -> _LT:
        return self._catalog[resolve_locale(language)]


def make_locale_lookup(catalog: dict[Locale, _LT]) -> "_LocaleLookup[_LT]":
    """Return a callable that maps a language string to *catalog* entry.

    Usage::

        get_foo_prompts = make_locale_lookup({
            Locale.ENGLISH: FooPrompts(...),
            Locale.RUSSIAN: FooPrompts(...),
        })
    """
    return _LocaleLookup(catalog)


def resolve_locale(language: str | None) -> Locale:
    """Map a free-form language string onto a :class:`Locale`.

    Unknown or empty strings fall back to :data:`DEFAULT_LOCALE` so
    prompt rendering never crashes on an unsupported language — the
    player still gets the English prompts with whatever label they
    chose, which is the least-surprising degradation.
    """
    if not language:
        return DEFAULT_LOCALE
    return _LOCALE_ALIASES.get(language.strip().lower(), DEFAULT_LOCALE)
