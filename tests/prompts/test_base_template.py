"""Unit tests for the composable prompt-template primitives.

These exercise ``PromptSection`` / ``PromptTemplate`` directly so mutation
testing on ``prompts/base_template.py`` has behavioral assertions to fail
against. The silent-skip-on-missing-var rule (a section whose required vars are
absent is dropped, not errored) is load-bearing for prompt safety, so it gets
explicit positive *and* negative coverage.
"""

from __future__ import annotations

import allure
import pytest

from prompts.base_template import PromptSection, PromptTemplate


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Prompt templating")
class TestPromptSectionRender:
    @allure.story("Section rendering")
    @allure.title("render interpolates every provided variable into the template")
    def test_interpolates_all_vars(self):
        section = PromptSection(
            name="greet",
            template="Hello, {name} of {place}!",
            required_vars=["name", "place"],
        )

        assert section.render(name="Ada", place="London") == "Hello, Ada of London!"

    @allure.story("Section rendering")
    @allure.title("render with no required_vars returns the literal template unchanged")
    def test_no_required_vars_returns_literal(self):
        section = PromptSection(name="static", template="A fixed line.")

        assert section.render() == "A fixed line."

    @allure.story("Section rendering")
    @allure.title("render ignores extra kwargs the template does not reference")
    def test_ignores_extra_kwargs(self):
        section = PromptSection(name="greet", template="Hi {name}", required_vars=["name"])

        assert section.render(name="Ada", unused="ignored") == "Hi Ada"

    @allure.story("Section validation")
    @allure.title("render raises ValueError naming the section and only the missing vars")
    def test_missing_var_message_lists_only_missing(self):
        section = PromptSection(name="profile", template="{first}/{second}", required_vars=["first", "second"])

        # The regex pins the section name and the exact missing list. ``first`` was
        # supplied, so a ``not in`` -> ``in`` flip (reporting ``first``) fails the match.
        with pytest.raises(ValueError, match=r"section 'profile': \['second'\]"):
            section.render(first="x")

    @allure.story("Section validation")
    @allure.title("render reports every missing var when none are supplied")
    def test_all_vars_missing_reported(self):
        section = PromptSection(name="multi", template="{a}{b}", required_vars=["a", "b"])

        with pytest.raises(ValueError, match=r"\['a', 'b'\]"):
            section.render()


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Prompt templating")
class TestPromptTemplateRender:
    @allure.story("Template composition")
    @allure.title("render joins satisfied sections with the default double-newline separator")
    def test_default_separator_joins_sections(self):
        template = PromptTemplate(
            [
                PromptSection(name="a", template="first"),
                PromptSection(name="b", template="second"),
            ]
        )

        assert template.render() == "first\n\nsecond"

    @allure.story("Template composition")
    @allure.title("render honors a custom separator between sections")
    def test_custom_separator(self):
        template = PromptTemplate(
            [
                PromptSection(name="a", template="first"),
                PromptSection(name="b", template="second"),
            ],
            separator=" | ",
        )

        assert template.render() == "first | second"

    @allure.story("Template composition")
    @allure.title("render silently skips sections whose required vars are absent")
    def test_skips_sections_with_missing_vars(self):
        template = PromptTemplate(
            [
                PromptSection(name="always", template="base"),
                PromptSection(name="scene", template="In {scene}", required_vars=["scene"]),
            ]
        )

        # No ValueError, and the unsatisfied section is dropped entirely.
        assert template.render() == "base"

    @allure.story("Template composition")
    @allure.title("render includes a section only when all of its required vars are present")
    def test_section_needs_all_required_vars(self):
        section = PromptSection(name="pair", template="{a}+{b}", required_vars=["a", "b"])
        template = PromptTemplate([section])

        # Partial context -> skipped (kills the ``all`` -> ``any`` mutant, which
        # would try to render and raise on the missing var).
        assert template.render(a="x") == ""
        # Full context -> rendered.
        assert template.render(a="x", b="y") == "x+y"

    @allure.story("Template composition")
    @allure.title("render returns an empty string when there are no sections")
    def test_empty_template_renders_empty(self):
        assert PromptTemplate().render() == ""
        assert PromptTemplate([]).render() == ""

    @allure.story("Template composition")
    @allure.title("the section list is copied so later mutation of the input does not leak in")
    def test_sections_input_is_copied(self):
        sections = [PromptSection(name="a", template="first")]
        template = PromptTemplate(sections)

        sections.append(PromptSection(name="b", template="leaked"))

        # If __init__ aliased the list instead of copying it, "leaked" would appear.
        assert template.render() == "first"


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Prompt templating")
class TestPromptTemplateMetadata:
    @allure.story("Required vars")
    @allure.title("required_vars is the union of every section's required vars")
    def test_required_vars_union(self):
        template = PromptTemplate(
            [
                PromptSection(name="a", template="{x}", required_vars=["x"]),
                PromptSection(name="b", template="{y}{z}", required_vars=["y", "z"]),
                PromptSection(name="static", template="none"),
            ]
        )

        assert template.required_vars == {"x", "y", "z"}

    @allure.story("Required vars")
    @allure.title("required_vars is an empty set when no section declares any")
    def test_required_vars_empty(self):
        template = PromptTemplate([PromptSection(name="static", template="none")])

        assert template.required_vars == set()

    @allure.story("Representation")
    @allure.title("repr lists the section names in order")
    def test_repr_lists_section_names(self):
        template = PromptTemplate(
            [
                PromptSection(name="intro", template="i"),
                PromptSection(name="body", template="b"),
            ]
        )

        assert repr(template) == "PromptTemplate(sections=['intro', 'body'])"
