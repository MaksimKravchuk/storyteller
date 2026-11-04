"""Shorter match forms for long NPC descriptors.

An unintroduced NPC's alias is a whole descriptive phrase ("Плечистый
мужчина с обветренным лицом и строгим взглядом", "a broad-shouldered man
with a weathered face"). The Narrator rarely repeats it verbatim — it
writes "плечистого мужчину" or just "the man" — so an exact lemma-sequence
match almost never fires and the NPC is never clickable in the prose.

:func:`short_forms` derives the shorter phrases the prose actually uses:
the *head* of the descriptor (everything before the first preposition,
conjunction or comma), the head trimmed to end at its first noun, and that
noun alone. Russian finds the noun with pymorphy3's part-of-speech tags;
other languages assume the head ends in its noun (English word order).
"""

from __future__ import annotations

import re

from formatting.entity_lemmatizers import Lemmatizer, NounTest
from models.visible_entity import VisibleEntity

TokenForm = tuple[str, ...]
OwnedForm = tuple[str, TokenForm]  # (entity id, tokens or lemmas)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# Words that end a descriptor's head phrase: what follows them qualifies
# the head ("мужчина [с обветренным лицом]", "a man [with a scar]").
_HEAD_BREAKERS = frozenset(
    # Russian prepositions, conjunctions and relative pronouns.
    "с со в во у на из под над без за к ко от по при о об обо перед возле около "
    "и или а но что который которая которое которые чей "
    # English prepositions, conjunctions and relative pronouns.
    "with in at on from under by near beside behind of and or but who whose which that "
    "wearing holding carrying".split(),
)
_ARTICLES = frozenset(("a", "an", "the"))


def short_forms(alias: str, is_noun: NounTest | None) -> list[TokenForm]:
    """Return shorter token sequences an alias may appear as in prose.

    The alias's own full token sequence is never included, and the result
    is ordered longest first without duplicates.
    """
    head = _head_tokens(alias)
    noun_idx = _noun_index(head, is_noun)
    if noun_idx < 0:
        return []
    full = tuple(_TOKEN_RE.findall(alias))
    forms: list[TokenForm] = []
    for form in _candidate_forms(head, noun_idx):
        if form != full and form not in forms:
            forms.append(form)
    return forms


def npc_short_forms(
    entities: list[VisibleEntity],
    is_noun: NounTest | None,
    lemmatize: Lemmatizer,
) -> list[OwnedForm]:
    """Return ``(entity_id, lemmas)`` for every short form of every NPC alias."""
    pairs: list[OwnedForm] = []
    for entity in entities:
        if entity.kind != "npc":
            continue
        for alias in entity.names:
            for form in short_forms(alias, is_noun):
                lemmas = tuple(map(lemmatize, form))
                pairs.append((entity.id, lemmas))
    return pairs


def _candidate_forms(head: list[str], noun_idx: int) -> list[TokenForm]:
    """Return the whole head, the head cut after its noun, and the noun alone."""
    through_noun = tuple(head[: noun_idx + 1])
    noun_alone = (head[noun_idx],)
    return [tuple(head), through_noun, noun_alone]


def _head_tokens(alias: str) -> list[str]:
    """Return the alias's leading tokens up to the first head-breaking word."""
    first_clause = alias.split(",", 1)[0]
    head: list[str] = []
    for token in _TOKEN_RE.findall(first_clause):
        if token.lower() in _HEAD_BREAKERS:
            break
        head.append(token)
    while head and head[0].lower() in _ARTICLES:
        head.pop(0)
    return head


def _noun_index(head: list[str], is_noun: NounTest | None) -> int:
    """Return the position of the head's noun, or -1 when the head has none.

    Without a noun test the head is assumed to end in its noun.
    """
    if is_noun is None:
        return len(head) - 1
    for idx, token in enumerate(head):
        if is_noun(token):
            return idx
    return -1
