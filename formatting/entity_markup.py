"""Wrap entity mentions in narrator HTML with clickable spans.

Runs after :func:`formatting.markdown_render.to_html` — walks the
rendered HTML's text nodes (never attribute values or existing tag
contents) and wraps any mention of a :class:`VisibleEntity` alias in a
``<span class="poi" data-kind="..." data-id="...">...</span>``.

Russian is the primary play language and is heavily inflected, so the
default matcher lemmatises both the aliases and each text-node token
with pymorphy3 and matches lemma sequences rather than surface forms
(see :mod:`formatting.entity_lemmatizers`). English uses a tiny
heuristic stemmer so the feature still adds value for Latin-alphabet
settings without pulling a second dependency.

If pymorphy3 is not importable at runtime, the matcher falls back to a
case-insensitive exact match. Missing optional deps must never brick
the render path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape

from formatting.entity_lemmatizers import Lemmatizer, pick_lemmatizer
from models.visible_entity import VisibleEntity

_TAG_RE = re.compile(r"<[^>]+>")
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_SPAN_TEMPLATE = '<span class="poi" data-kind="{kind}" data-id="{entity_id}">{body}</span>'


@dataclass(frozen=True)
class _AliasPlan:
    """One alias's match plan: entity id, kind, and lemma sequence."""

    entity_id: str
    kind: str
    lemmas: tuple[str, ...]


def wrap_entities(
    html: str,
    entities: list[VisibleEntity],
    language: str,
) -> str:
    """Return ``html`` with entity-alias mentions wrapped in clickable spans.

    The input must be the output of
    :func:`formatting.markdown_render.to_html` (or an equivalently-
    escaped fragment) — we rely on HTML escaping having already
    neutralised any player-controlled content.
    """
    if not html or not entities:
        return html
    lemmatize = pick_lemmatizer(language)
    plans = _build_plans(entities, lemmatize)
    if not plans:
        return html
    return _Rewriter(plans, lemmatize).rewrite(html)


def _build_plans(entities: list[VisibleEntity], lemmatize: Lemmatizer) -> list[_AliasPlan]:
    """Flatten every alias into a lemma-sequence plan, longest first."""
    plans: list[_AliasPlan] = []
    for entity in entities:
        for alias in entity.names:
            lemmas = tuple(lemmatize(tok) for tok in _TOKEN_RE.findall(alias))
            if not lemmas:
                continue
            plans.append(_AliasPlan(entity_id=entity.id, kind=entity.kind, lemmas=lemmas))
    plans.sort(key=lambda plan: len(plan.lemmas), reverse=True)
    return plans


class _Rewriter:
    """Walks HTML text nodes and rewrites alias hits into entity spans."""

    def __init__(self, plans: list[_AliasPlan], lemmatize: Lemmatizer) -> None:
        self._plans = plans
        self._lemmatize = lemmatize
        # Memoize lemmatized prose tokens within one rewrite call —
        # pymorphy3.parse is the dominant per-token cost on Russian turns
        # and typical prose repeats many common words.
        self._lemma_cache: dict[str, str] = {}

    def rewrite(self, html: str) -> str:
        """Replace alias hits inside HTML text nodes, leaving tags untouched."""
        parts: list[str] = []
        cursor = 0
        for match in _TAG_RE.finditer(html):
            parts.append(self._rewrite_chunk(html[cursor : match.start()]))
            parts.append(match.group(0))
            cursor = match.end()
        parts.append(self._rewrite_chunk(html[cursor:]))
        return "".join(parts)

    def _rewrite_chunk(self, chunk: str) -> str:
        """Rewrite a raw text chunk (no HTML tags inside) with entity spans."""
        if not chunk:
            return chunk
        tokens = list(_TOKEN_RE.finditer(chunk))
        if not tokens:
            return chunk
        lemmas = [self._lemma_of(match.group(0)) for match in tokens]
        return _apply_replacements(chunk, self._find_replacements(tokens, lemmas))

    def _find_replacements(
        self,
        tokens: list[re.Match[str]],
        lemmas: list[str],
    ) -> list[tuple[int, int, _AliasPlan]]:
        """Walk tokens left-to-right and collect ``(start, end, plan)`` hits."""
        hits: list[tuple[int, int, _AliasPlan]] = []
        consumed = 0
        for idx, token in enumerate(tokens):
            hit = self._match_at(tokens, lemmas, idx, consumed)
            if hit is None:
                continue
            hits.append(hit)
            consumed = hit[1]
        return hits

    def _match_at(
        self,
        tokens: list[re.Match[str]],
        lemmas: list[str],
        idx: int,
        consumed: int,
    ) -> tuple[int, int, _AliasPlan] | None:
        """Return the ``(start, end, plan)`` hit at ``idx`` if the gate allows it."""
        token = tokens[idx]
        if token.start() < consumed:
            return None
        plan = self._first_match(lemmas, idx)
        if plan is None:
            return None
        end = tokens[idx + len(plan.lemmas) - 1].end()
        return (token.start(), end, plan)

    def _first_match(self, lemmas: list[str], start_idx: int) -> _AliasPlan | None:
        """Return the longest alias plan whose lemma sequence starts at ``start_idx``."""
        for plan in self._plans:
            end_idx = start_idx + len(plan.lemmas)
            if end_idx > len(lemmas):
                continue
            if tuple(lemmas[start_idx:end_idx]) == plan.lemmas:
                return plan
        return None

    def _lemma_of(self, token: str) -> str:
        cached = self._lemma_cache.get(token)
        if cached is not None:
            return cached
        lemma = self._lemmatize(token)
        self._lemma_cache[token] = lemma
        return lemma


def _apply_replacements(
    chunk: str,
    replacements: list[tuple[int, int, _AliasPlan]],
) -> str:
    """Substitute the given ``(start, end, plan)`` spans into ``chunk``."""
    if not replacements:
        return chunk
    parts: list[str] = []
    cursor = 0
    for start, end, plan in replacements:
        parts.append(chunk[cursor:start])
        parts.append(
            _SPAN_TEMPLATE.format(
                kind=escape(plan.kind, quote=True),
                entity_id=escape(plan.entity_id, quote=True),
                body=chunk[start:end],
            ),
        )
        cursor = end
    parts.append(chunk[cursor:])
    return "".join(parts)
