"""Tests for the Markdown → platform converter."""

from __future__ import annotations

import allure
import pytest

from formatting.markdown_render import render, to_html, to_plain, to_telegram_html
from formatting.platform import ClientPlatform


@allure.epic("Narrative Delivery")
@allure.feature("Markdown rendering")
class TestToTelegramHtml:
    @allure.story("Telegram HTML")
    @allure.title("Markdown **bold** converts to Telegram <b> tags")
    def test_bold(self):
        assert to_telegram_html("Hello **world**.") == "Hello <b>world</b>."

    @allure.story("Telegram HTML")
    @allure.title("Markdown *italic* with single asterisks converts to Telegram <i> tags")
    def test_italic_star(self):
        assert to_telegram_html("The *wind* blows.") == "The <i>wind</i> blows."

    @allure.story("Telegram HTML")
    @allure.title("Markdown _italic_ with underscores converts to Telegram <i> tags")
    def test_italic_underscore(self):
        assert to_telegram_html("A _quiet_ room.") == "A <i>quiet</i> room."

    @allure.story("Telegram HTML")
    @allure.title("Markdown inline `code` converts to Telegram <code> tags")
    def test_code(self):
        assert to_telegram_html("Sign reads `Beware`.") == "Sign reads <code>Beware</code>."

    @allure.story("Telegram HTML")
    @allure.title("Telegram HTML renderer escapes <, >, and & as HTML entities")
    def test_escapes_html_special_chars(self):
        assert to_telegram_html("5 < 6 & 7 > 3") == "5 &lt; 6 &amp; 7 &gt; 3"

    @allure.story("Telegram HTML")
    @allure.title("HTML-special characters inside inline code spans are escaped before wrapping in <code>")
    def test_escapes_inside_code(self):
        assert to_telegram_html("`<script>`") == "<code>&lt;script&gt;</code>"

    @allure.story("Telegram HTML")
    @allure.title("Bold and italic markers inside inline code spans are preserved as literal text")
    def test_code_span_protects_markers(self):
        # Inside code, the **bold** markers stay literal.
        assert to_telegram_html("`**not bold**`") == "<code>**not bold**</code>"

    @allure.story("Telegram HTML")
    @allure.title("Blank-line paragraph breaks in Markdown are preserved verbatim in Telegram HTML output")
    def test_paragraphs_separated_by_blank_line(self):
        md = "First paragraph.\n\nSecond paragraph."
        assert to_telegram_html(md) == "First paragraph.\n\nSecond paragraph."

    @allure.story("Telegram HTML")
    @allure.title("A sentence mixing bold and italic Markdown renders both tag styles in the same output")
    def test_mixed(self):
        md = "You meet **Marcus**. He whispers *softly*."
        expected = "You meet <b>Marcus</b>. He whispers <i>softly</i>."
        assert to_telegram_html(md) == expected

    @allure.story("Telegram HTML")
    @allure.title("Empty Markdown input produces an empty Telegram HTML string")
    def test_empty(self):
        assert to_telegram_html("") == ""

    @allure.story("Telegram HTML")
    @allure.title("Unbalanced bold markers are passed through as literal asterisks rather than broken tags")
    def test_unbalanced_bold_left_alone(self):
        assert to_telegram_html("a **b c") == "a **b c"


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


@allure.epic("Narrative Delivery")
@allure.feature("Markdown rendering")
class TestToPlain:
    @allure.story("Plain text")
    @allure.title("Plain-text renderer strips **bold** markers and keeps only the inner text")
    def test_strips_bold(self):
        assert to_plain("Hello **world**.") == "Hello world."

    @allure.story("Plain text")
    @allure.title("Plain-text renderer strips *italic* markers and keeps only the inner text")
    def test_strips_italic(self):
        assert to_plain("The *wind* blows.") == "The wind blows."

    @allure.story("Plain text")
    @allure.title("Plain-text renderer strips underscore-style _italic_ markers")
    def test_strips_underscore_italic(self):
        assert to_plain("A _quiet_ room.") == "A quiet room."

    @allure.story("Plain text")
    @allure.title("Plain-text renderer strips backticks but preserves the content inside code spans")
    def test_keeps_code_content(self):
        assert to_plain("Sign: `Beware`.") == "Sign: Beware."

    @allure.story("Plain text")
    @allure.title("Plain-text renderer does not HTML-escape special characters since the output is not HTML")
    def test_does_not_escape_html(self):
        assert to_plain("5 < 6 & 7") == "5 < 6 & 7"

    @allure.story("Plain text")
    @allure.title("Plain-text renderer preserves blank-line paragraph breaks as-is")
    def test_paragraphs(self):
        assert to_plain("a\n\nb") == "a\n\nb"

    @allure.story("Plain text")
    @allure.title("Plain-text renderer returns an empty string when given empty Markdown")
    def test_empty(self):
        assert to_plain("") == ""


@allure.epic("Narrative Delivery")
@allure.feature("Markdown rendering")
class TestRenderDispatcher:
    @allure.story("Platform dispatch")
    @allure.title("The render() dispatcher produces the correct output for each ClientPlatform variant")
    @pytest.mark.parametrize(
        ("platform", "expected"),
        [
            (ClientPlatform.PLAIN, "Hi bold and italic."),
            (ClientPlatform.TELEGRAM_HTML, "Hi <b>bold</b> and <i>italic</i>."),
            (ClientPlatform.HTML, "<p>Hi <strong>bold</strong> and <em>italic</em>.</p>"),
        ],
    )
    def test_render(self, platform, expected):
        assert render("Hi **bold** and *italic*.", platform) == expected
