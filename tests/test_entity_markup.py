"""Tests for :func:`formatting.entity_markup.wrap_entities`.

Verifies that the deterministic post-match wraps alias hits in
``<span class="poi">`` markers, respects HTML tag boundaries, resolves
overlapping aliases longest-first, and crucially handles Russian
inflection via pymorphy3 so "вооружённый мужчина" matches every
grammatical case the narrator produces.
"""

from __future__ import annotations

import allure

from formatting.entity_markup import wrap_entities
from models.visible_entity import VisibleEntity

_NPC = VisibleEntity(kind="npc", id="npc-1", names=["an armed man"])
_NPC_RU = VisibleEntity(kind="npc", id="npc-1", names=["вооружённый мужчина"])
_NPC_INTRODUCED = VisibleEntity(
    kind="npc",
    id="npc-1",
    names=["Tony (Watchman)", "Tony", "the watchman"],
)
_POI = VisibleEntity(kind="poi", id="poi-1", names=["fireplace", "the hearth"])


@allure.epic("Narrator & UI")
@allure.feature("Entity markup post-match")
class TestWrapEntities:
    @allure.story("English")
    @allure.title("A single English alias is wrapped with the entity's kind and id")
    def test_english_basic(self):
        html = "<p>You see an armed man by the door.</p>"
        wrapped = wrap_entities(html, [_NPC], "English")
        assert '<span class="poi" data-kind="npc" data-id="npc-1">an armed man</span>' in wrapped

    @allure.story("Multiple aliases")
    @allure.title("Any alias of an introduced NPC wraps with the same entity id")
    def test_any_alias_wraps(self):
        html = "<p>The watchman nods. Tony leans on his spear.</p>"
        wrapped = wrap_entities(html, [_NPC_INTRODUCED], "English")
        assert wrapped.count('data-id="npc-1"') == 2

    @allure.story("Longest-first")
    @allure.title("Longest alias wins when a shorter alias is a subsequence")
    def test_longest_first(self):
        ambiguous = VisibleEntity(kind="npc", id="npc-1", names=["Tony", "armed man", "Tony the armed man"])
        html = "<p>Tony the armed man approaches.</p>"
        wrapped = wrap_entities(html, [ambiguous], "English")
        assert wrapped.count('data-id="npc-1"') == 1
        assert "Tony the armed man</span>" in wrapped

    @allure.story("HTML safety")
    @allure.title("Matches inside tag attributes are never rewritten")
    def test_no_rewrite_inside_tags(self):
        entity = VisibleEntity(kind="poi", id="poi-x", names=["bar"])
        html = '<p class="bar">The bar is empty.</p>'
        wrapped = wrap_entities(html, [entity], "English")
        # The class attribute must survive unchanged; the word "bar" inside <p> text is wrapped.
        assert 'class="bar"' in wrapped
        assert 'data-id="poi-x">bar</span>' in wrapped

    @allure.story("Russian")
    @allure.title("A Russian alias matches every grammatical case via lemmatization")
    def test_russian_inflections(self):
        case_forms = [
            "вооружённый мужчина стоит у двери",
            "ты видишь вооружённого мужчину",
            "ты подходишь к вооружённому мужчине",
            "ты говоришь с вооружённым мужчиной",
            "ты вспоминаешь о вооружённом мужчине",
        ]
        for form in case_forms:
            html = "<p>{0}.</p>".format(form)
            wrapped = wrap_entities(html, [_NPC_RU], "Russian")
            assert 'data-id="npc-1"' in wrapped, "no match in case form: {0}".format(form)

    @allure.story("Empty inputs")
    @allure.title("Empty html returns empty, empty entity list returns the html unchanged")
    def test_empty_inputs(self):
        assert wrap_entities("", [_NPC], "English") == ""
        assert wrap_entities("<p>hi</p>", [], "English") == "<p>hi</p>"

    @allure.story("POI alias")
    @allure.title("POI aliases both match to the same entity id")
    def test_poi_aliases(self):
        html = "<p>A fireplace crackles; the hearth is warm.</p>"
        wrapped = wrap_entities(html, [_POI], "English")
        assert wrapped.count('data-id="poi-1"') == 2

    @allure.story("Russian")
    @allure.title("A single-word match does NOT wrap a multi-word alias: lemma order matters")
    def test_russian_partial_alias_does_not_wrap(self):
        # The narrator says "Мужчина стоит" — just "man". An alias of
        # "вооружённый мужчина" (armed man) must NOT match the bare
        # "мужчина" because the full lemma sequence isn't there.
        html = "<p>Мужчина стоит у двери.</p>"
        wrapped = wrap_entities(html, [_NPC_RU], "Russian")
        assert "data-id=" not in wrapped

    @allure.story("Multiple entities")
    @allure.title("When two entities share an alias the longest-first sort breaks the tie deterministically")
    def test_shared_alias_across_entities_is_deterministic(self):
        first = VisibleEntity(kind="npc", id="npc-first", names=["captain"])
        second = VisibleEntity(kind="npc", id="npc-second", names=["captain"])
        html = "<p>The captain waits.</p>"
        wrapped = wrap_entities(html, [first, second], "English")
        # Registration order wins when alias lengths tie (sort is stable).
        assert 'data-id="npc-first"' in wrapped
        assert 'data-id="npc-second"' not in wrapped

    @allure.story("Token cache")
    @allure.title("Passing a shared token_cache across two calls preserves correctness and fills the cache")
    def test_shared_token_cache_reused_across_calls(self):
        cache: dict[str, str] = {}
        entity = VisibleEntity(kind="npc", id="npc-1", names=["вооружённый мужчина"])
        first = wrap_entities("<p>вооружённого мужчину видно.</p>", [entity], "Russian", cache)
        cache_size_after_first = len(cache)
        second = wrap_entities("<p>вооружённого мужчину видно снова.</p>", [entity], "Russian", cache)
        assert 'data-id="npc-1"' in first
        assert 'data-id="npc-1"' in second
        # Russian tokens carry into the shared cache; the repeated call does
        # not clear nor mis-cache entries.
        assert len(cache) >= cache_size_after_first
