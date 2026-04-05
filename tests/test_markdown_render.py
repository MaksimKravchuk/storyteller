"""Tests for the Markdown → platform converter."""

from __future__ import annotations

import pytest

from formatting.markdown_render import render, to_html, to_plain, to_telegram_html
from formatting.platform import ClientPlatform


class TestToTelegramHtml:
    def test_bold(self):
        assert to_telegram_html("Hello **world**.") == "Hello <b>world</b>."

    def test_italic_star(self):
        assert to_telegram_html("The *wind* blows.") == "The <i>wind</i> blows."

    def test_italic_underscore(self):
        assert to_telegram_html("A _quiet_ room.") == "A <i>quiet</i> room."

    def test_code(self):
        assert to_telegram_html("Sign reads `Beware`.") == "Sign reads <code>Beware</code>."

    def test_escapes_html_special_chars(self):
        assert to_telegram_html("5 < 6 & 7 > 3") == "5 &lt; 6 &amp; 7 &gt; 3"

    def test_escapes_inside_code(self):
        assert to_telegram_html("`<script>`") == "<code>&lt;script&gt;</code>"

    def test_code_span_protects_markers(self):
        # Inside code, the **bold** markers stay literal.
        assert to_telegram_html("`**not bold**`") == "<code>**not bold**</code>"

    def test_paragraphs_separated_by_blank_line(self):
        md = "First paragraph.\n\nSecond paragraph."
        assert to_telegram_html(md) == "First paragraph.\n\nSecond paragraph."

    def test_mixed(self):
        md = "You meet **Marcus**. He whispers *softly*."
        expected = "You meet <b>Marcus</b>. He whispers <i>softly</i>."
        assert to_telegram_html(md) == expected

    def test_empty(self):
        assert to_telegram_html("") == ""

    def test_unbalanced_bold_left_alone(self):
        assert to_telegram_html("a **b c") == "a **b c"


class TestToHtml:
    def test_wraps_paragraphs(self):
        md = "First.\n\nSecond."
        assert to_html(md) == "<p>First.</p>\n<p>Second.</p>"

    def test_strong_and_em(self):
        assert to_html("**x** *y*") == "<p><strong>x</strong> <em>y</em></p>"

    def test_escapes_angle_brackets(self):
        assert to_html("a < b") == "<p>a &lt; b</p>"


class TestToPlain:
    def test_strips_bold(self):
        assert to_plain("Hello **world**.") == "Hello world."

    def test_strips_italic(self):
        assert to_plain("The *wind* blows.") == "The wind blows."

    def test_strips_underscore_italic(self):
        assert to_plain("A _quiet_ room.") == "A quiet room."

    def test_keeps_code_content(self):
        assert to_plain("Sign: `Beware`.") == "Sign: Beware."

    def test_does_not_escape_html(self):
        assert to_plain("5 < 6 & 7") == "5 < 6 & 7"

    def test_paragraphs(self):
        assert to_plain("a\n\nb") == "a\n\nb"

    def test_empty(self):
        assert to_plain("") == ""


class TestRenderDispatcher:
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
