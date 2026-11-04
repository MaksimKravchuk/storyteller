"""Ambiguity filter for derived NPC short forms.

A short form ("мужчина", "потёртый тулуп") is only safe to link when it
can mean one person: no other NPC derives the same form, and it does not
occur inside any other entity's full alias — otherwise "писарь в
потёртом тулупе" would light up as the woman whose descriptor starts
with "Потёртый тулуп".
"""

from __future__ import annotations

from formatting.entity_short_forms import OwnedForm, TokenForm


def unambiguous_forms(owned: list[OwnedForm], full_aliases: list[OwnedForm]) -> list[OwnedForm]:
    """Keep the forms owned by one entity alone and found in no other entity's full alias."""
    kept: list[OwnedForm] = []
    for form, ids in _owners_by_form(owned).items():
        pair = (min(ids), form)
        if len(ids) == 1 and not _inside_other_alias(pair, full_aliases):
            kept.append(pair)
    return kept


def _owners_by_form(owned: list[OwnedForm]) -> dict[TokenForm, set[str]]:
    owners: dict[TokenForm, set[str]] = {}
    for entity_id, form in owned:
        owners.setdefault(form, set()).add(entity_id)
    return owners


def _inside_other_alias(pair: OwnedForm, full_aliases: list[OwnedForm]) -> bool:
    owner, form = pair
    others = (alias for entity_id, alias in full_aliases if entity_id != owner)
    return any(_contains_run(alias, form) for alias in others)


def _contains_run(haystack: TokenForm, needle: TokenForm) -> bool:
    """Return whether ``needle`` occurs as a contiguous run inside ``haystack``."""
    width = len(needle)
    for start in range(len(haystack) - width + 1):
        if haystack[start : start + width] == needle:
            return True
    return False
