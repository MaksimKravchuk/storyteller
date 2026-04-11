"""Tests for openai_client._sanitize — ensure problematic characters are removed."""

from __future__ import annotations

import allure
import pytest

from llm.openai_client import _sanitize

pytestmark = [allure.epic("Engine & LLM Infrastructure"), allure.feature("OpenAI client sanitization")]


@allure.story("Control character stripping")
@allure.title(
    "_sanitize strips null bytes, C0 control characters, and DEL while preserving text, tabs, newlines, and Unicode"
)
@pytest.mark.parametrize(
    "input_text, expected",
    [
        # Null byte stripped
        ("hello\x00world", "helloworld"),
        # Only null bytes
        ("\x00\x00", ""),
        # Null byte at start/end
        ("\x00hello\x00", "hello"),
        # Normal text unchanged
        ("hello world", "hello world"),
        # Tab, newline, CR preserved
        ("line1\nline2\ttab\rcarriage", "line1\nline2\ttab\rcarriage"),
        # Other C0 control characters stripped (BEL, BS, VT, FF, ESC, etc.)
        ("a\x07\x08\x0b\x0c\x1b\x1fz", "az"),
        # DEL (0x7F) stripped
        ("abc\x7fdef", "abcdef"),
        # Unicode non-ASCII preserved
        ("Привет мир 🌍", "Привет мир 🌍"),
        # Empty string
        ("", ""),
    ],
)
def test_sanitize(input_text: str, expected: str) -> None:
    assert _sanitize(input_text) == expected


# Split out from the parametrize table because allure-pytest's JSON writer
# cannot serialize parametrize values containing lone UTF-16 surrogates.
@allure.story("Control character stripping")
@allure.title("_sanitize replaces a lone UTF-16 surrogate with three U+FFFD replacement characters")
def test_sanitize_lone_surrogate() -> None:
    assert _sanitize("test\x00\ud800end") == "test\ufffd\ufffd\ufffdend"
