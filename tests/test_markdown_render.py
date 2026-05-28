"""Tests for the Markdown to HTML converter."""

from __future__ import annotations

import allure
from formatting.markdown_render import to_html


@allure.epic("Narrative Delivery")
@allure.feature("Markdown rendering")
class TestToHtml:
    @allure.story("HTML output")
    @allure.title("Generic HTML renderer wraps each paragraph of Markdown in a <p> tag")
    def test_wraps_paragraphs(self):
        md = "First.\n\nSecond."
        assert to_html(md) == "<p>First.</p>\n<p>Second.</p>"

    @allure.story("HTML output")
    @allure.title("Generic HTML renderer emits <strong> for bold and <em> for italic Markdown")
    def test_strong_and_em(self):
        assert to_html("**x** *y*") == "<p><strong>x</strong> <em>y</em></p>"

    @allure.story("HTML output")
    @allure.title("Generic HTML renderer escapes angle brackets inside paragraphs as HTML entities")
    def test_escapes_angle_brackets(self):
        assert to_html("a < b") == "<p>a &lt; b</p>"

    @allure.story("HTML output")
    @allure.title("HTML-special characters inside inline code spans are escaped before wrapping in <code>")
    def test_escapes_inside_code(self):
        assert to_html("`<script>`") == "<p><code>&lt;script&gt;</code></p>"

    @allure.story("HTML output")
    @allure.title("Bold and italic markers inside inline code spans are preserved as literal text")
    def test_code_span_protects_markers(self):
        assert to_html("`**not bold**`") == "<p><code>**not bold**</code></p>"

    @allure.story("HTML output")
    @allure.title("Empty Markdown input produces an empty HTML string")
    def test_empty(self):
        assert to_html("") == ""

    @allure.story("HTML output")
    @allure.title("Unbalanced bold markers are passed through as literal asterisks rather than broken tags")
    def test_unbalanced_bold_left_alone(self):
        assert to_html("a **b c") == "<p>a **b c</p>"
