"""Legacy unit tests for the tag-based Actor output parser.

These cover :func:`cast.actor_tags.extract_revealed` and
:func:`cast.actor_tags.strip_trailing_tags` — the regex extraction layer
that is now superseded by the JSON envelope path.  The module is kept as
a deprecated shim to support ``envelope_mode=False`` rollbacks.

Originally part of ``tests/test_actor_revealed.py``; moved here when the
main test file was refactored to target the envelope path.
"""

from __future__ import annotations

import allure

from cast.actor_tags import extract_revealed, strip_trailing_tags


@allure.epic("NPC Interaction")
@allure.feature("Legacy tag extraction")
class TestExtractRevealed:
    @allure.story("Revealed tag regex")
    @allure.title("A single [REVEALED: self] token resolves to ``['self']`` and is stripped from the text")
    def test_single_self_token(self):
        text, tokens = extract_revealed("I am Marcus.\n[REVEALED: self]")
        assert tokens == ["self"]
        assert "[REVEALED:" not in text

    @allure.story("Revealed tag regex")
    @allure.title("A multi-token [REVEALED: self, Cassia] tag splits on commas and trims whitespace")
    def test_multiple_tokens(self):
        text, tokens = extract_revealed("I am Marcus, and that is Cassia.\n[REVEALED: self, Cassia]")
        assert tokens == ["self", "Cassia"]
        assert "[REVEALED:" not in text

    @allure.story("Revealed tag regex")
    @allure.title("Tokens with extra surrounding whitespace are stripped")
    def test_tokens_whitespace_trimmed(self):
        _, tokens = extract_revealed("Greetings.\n[REVEALED:   self ,   Cassia  ]")
        assert tokens == ["self", "Cassia"]

    @allure.story("Revealed tag regex")
    @allure.title("A response without any [REVEALED:] tag returns an empty list and unchanged text")
    def test_no_tag_returns_empty(self):
        text, tokens = extract_revealed("Just a line.")
        assert tokens == []
        assert text == "Just a line."

    @allure.story("Revealed tag regex")
    @allure.title("A malformed [REVEALED:] tag with an empty body yields an empty token list")
    def test_empty_body_returns_empty(self):
        text, tokens = extract_revealed("Hmm.\n[REVEALED: ]")
        assert tokens == []
        assert "[REVEALED:" not in text

    @allure.story("Revealed tag regex")
    @allure.title("A [REVEALED:] tag not anchored at end-of-string is ignored")
    def test_tag_not_at_end_is_ignored(self):
        raw = "[REVEALED: self]\nContinuing conversation."
        text, tokens = extract_revealed(raw)
        assert tokens == []
        assert text == raw


@allure.epic("NPC Interaction")
@allure.feature("Legacy tag extraction")
class TestStripTrailingTagsOrderIndependence:
    """The LLM can emit MOOD / STATUS / REVEALED in any sequence.

    The single-pass anchored extractors only strip the outermost tag;
    the loop in :func:`strip_trailing_tags` guarantees every trailing
    tag is captured regardless of ordering.
    """

    @allure.story("Multi-tag permutation")
    @allure.title("STATUS then REVEALED then MOOD — all three tags are captured and text is clean")
    def test_status_revealed_mood_permutation(self):
        bag = strip_trailing_tags("*winces*\n[STATUS: wounded]\n[REVEALED: self]\n[MOOD: wary]")
        assert bag.mood == "wary"
        assert bag.status == "wounded"
        assert bag.revealed == ["self"]
        assert "[STATUS:" not in bag.text
        assert "[MOOD:" not in bag.text
        assert "[REVEALED:" not in bag.text
        assert bag.text.strip() == "*winces*"

    @allure.story("Multi-tag permutation")
    @allure.title("MOOD then STATUS then REVEALED — extraction still captures all three")
    def test_mood_status_revealed_permutation(self):
        bag = strip_trailing_tags("Hail.\n[MOOD: friendly]\n[STATUS: healthy]\n[REVEALED: self, Cassia]")
        assert bag.mood == "friendly"
        assert bag.status == "healthy"
        assert bag.revealed == ["self", "Cassia"]

    @allure.story("Multi-tag permutation")
    @allure.title("Only one tag trailing — the loop captures it and leaves the others as None")
    def test_only_one_tag(self):
        bag = strip_trailing_tags("I am Marcus.\n[REVEALED: self]")
        assert bag.mood is None
        assert bag.status is None
        assert bag.revealed == ["self"]

    @allure.story("Multi-tag permutation")
    @allure.title("No trailing tags returns (text, None, None, [])")
    def test_no_tags(self):
        bag = strip_trailing_tags("Just a sentence.")
        assert bag.text == "Just a sentence."
        assert bag.mood is None
        assert bag.status is None
        assert bag.revealed == []

    @allure.story("Multi-tag permutation")
    @allure.title("Duplicate [MOOD:] tags collapse to the first/outermost value and both are stripped from text")
    def test_duplicate_mood_first_wins(self):
        bag = strip_trailing_tags("Back off!\n[MOOD: angry]\n[MOOD: calm]")
        assert bag.mood == "calm"
        assert "[MOOD:" not in bag.text
        assert bag.text.strip() == "Back off!"
