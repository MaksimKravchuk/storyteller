"""TDD tests for TextStyler — platform-aware text formatting."""

from __future__ import annotations


from interfaces.formatting_backends import (
    PlainTextBackend,
    TelegramHTMLBackend,
)
from interfaces.text_styler import SegmentType, TextStyler


# ── Phase 1: Parsing ─────────────────────────────────────────────────


class TestParsingPlainText:
    def test_parse_plain_text_returns_single_plain_segment(self):
        styler = TextStyler(PlainTextBackend())
        segments = styler.parse("The sun sets over the hills.")
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.PLAIN
        assert segments[0].text == "The sun sets over the hills."

    def test_parse_empty_string(self):
        styler = TextStyler(PlainTextBackend())
        segments = styler.parse("")
        assert not segments


class TestParsingDialogue:
    def test_parse_quoted_dialogue_detected(self):
        styler = TextStyler(PlainTextBackend())
        segments = styler.parse('You hear a voice. "Hello there," someone says.')
        types = [seg.segment_type for seg in segments]
        assert SegmentType.DIALOGUE in types
        dialogue = [seg for seg in segments if seg.segment_type == SegmentType.DIALOGUE]
        assert any('"Hello there,"' in dlg.text for dlg in dialogue)

    def test_parse_npc_name_before_speech_verb(self):
        styler = TextStyler(PlainTextBackend())
        segments = styler.parse('Marcus says: "Halt!"')
        types = [seg.segment_type for seg in segments]
        assert SegmentType.NPC_NAME in types
        assert SegmentType.DIALOGUE in types
        npc = [seg for seg in segments if seg.segment_type == SegmentType.NPC_NAME]
        assert any("Marcus" in npc_seg.text for npc_seg in npc)

    def test_parse_npc_name_after_speech_verb(self):
        """Handle patterns like: 'said Marcus' or '"Hello," whispered the guard.'"""
        styler = TextStyler(PlainTextBackend())
        segments = styler.parse('"Welcome," said Marcus.')
        types = [seg.segment_type for seg in segments]
        assert SegmentType.DIALOGUE in types
        assert SegmentType.NPC_NAME in types

    def test_parse_multiple_dialogues(self):
        styler = TextStyler(PlainTextBackend())
        text = 'Marcus says: "Hello." Livia replies: "Greetings."'
        segments = styler.parse(text)
        dialogues = [seg for seg in segments if seg.segment_type == SegmentType.DIALOGUE]
        assert len(dialogues) == 2

    def test_parse_speech_verbs_varied(self):
        """Test recognition of various speech verbs: whispered, shouted, etc."""
        styler = TextStyler(PlainTextBackend())
        for verb in ("whispered", "shouted", "exclaimed", "muttered", "replied"):
            text = f'Guard {verb}: "Stop right there!"'
            segments = styler.parse(text)
            types = [seg.segment_type for seg in segments]
            assert SegmentType.NPC_NAME in types, f"Failed for verb: {verb}"
            assert SegmentType.DIALOGUE in types, f"Failed for verb: {verb}"


class TestParsingSceneHeader:
    def test_parse_scene_header_short_first_line(self):
        """Short first line followed by blank line + paragraph = scene header."""
        styler = TextStyler(PlainTextBackend())
        text = (
            "The Forum Romanum\n\n"
            "You step into the bustling heart of ancient Rome. Merchants hawk their wares beneath marble columns."
        )
        segments = styler.parse(text)
        types = [seg.segment_type for seg in segments]
        assert SegmentType.SCENE_HEADER in types
        header = [seg for seg in segments if seg.segment_type == SegmentType.SCENE_HEADER]
        assert header[0].text == "The Forum Romanum"

    def test_long_first_line_not_treated_as_header(self):
        """A long first line should NOT be detected as a scene header."""
        styler = TextStyler(PlainTextBackend())
        text = (
            "You walk through the long and winding cobblestone streets of the ancient city,"
            " taking in every detail of the architecture.\n\nThe sun beats down overhead."
        )
        segments = styler.parse(text)
        types = [seg.segment_type for seg in segments]
        assert SegmentType.SCENE_HEADER not in types


class TestParsingSectionSeparator:
    def test_parse_section_separator_dashes(self):
        styler = TextStyler(PlainTextBackend())
        text = "First paragraph.\n\n---\n\nSecond paragraph."
        segments = styler.parse(text)
        types = [seg.segment_type for seg in segments]
        assert SegmentType.SECTION_SEPARATOR in types

    def test_parse_section_separator_asterisks(self):
        styler = TextStyler(PlainTextBackend())
        text = "First paragraph.\n\n***\n\nSecond paragraph."
        segments = styler.parse(text)
        types = [seg.segment_type for seg in segments]
        assert SegmentType.SECTION_SEPARATOR in types


# ── Phase 2: Backends ────────────────────────────────────────────────


class TestTelegramHTMLBackend:
    def test_bold_wraps_in_b_tags(self):
        backend = TelegramHTMLBackend()
        assert backend.bold("Marcus") == "<b>Marcus</b>"

    def test_italic_wraps_in_i_tags(self):
        backend = TelegramHTMLBackend()
        assert backend.italic("whisper") == "<i>whisper</i>"

    def test_escapes_html_entities(self):
        backend = TelegramHTMLBackend()
        assert backend.escape("5 < 10 & 10 > 5") == "5 &lt; 10 &amp; 10 &gt; 5"

    def test_separator(self):
        backend = TelegramHTMLBackend()
        sep = backend.separator()
        assert len(sep.strip()) > 0  # Non-empty separator


class TestPlainTextBackend:
    def test_bold_passes_through(self):
        backend = PlainTextBackend()
        assert backend.bold("Marcus") == "Marcus"

    def test_italic_passes_through(self):
        backend = PlainTextBackend()
        assert backend.italic("whisper") == "whisper"

    def test_escape_passes_through(self):
        backend = PlainTextBackend()
        assert backend.escape("5 < 10") == "5 < 10"

    def test_separator(self):
        backend = PlainTextBackend()
        sep = backend.separator()
        assert len(sep.strip()) > 0


# ── Phase 3: Full format() ───────────────────────────────────────────


class TestFormatTelegram:
    def test_format_full_scene_telegram(self):
        """Realistic narrator output with scene header and dialogue."""
        styler = TextStyler(TelegramHTMLBackend())
        text = (
            "The Roman Forum\n\n"
            "You step into the bustling heart of the city. Merchants shout their prices "
            "while senators hurry past in white togas.\n\n"
            'Marcus says: "Welcome, stranger. What brings you here?"'
        )
        formatted_text = styler.format(text)
        # Scene header should be bold
        assert "<b>The Roman Forum</b>" in formatted_text
        # NPC name should be bold
        assert "<b>Marcus</b>" in formatted_text
        # Dialogue should be italic
        assert "<i>" in formatted_text
        # HTML entities in plain text should be escaped (no raw < or >)
        # The original text has no < or >, so just check structure
        assert "</b>" in formatted_text

    def test_format_continuation_with_dialogue(self):
        styler = TextStyler(TelegramHTMLBackend())
        text = 'The guard eyes you suspiciously. "State your business," he growls.'
        formatted_text = styler.format(text)
        assert "<i>" in formatted_text  # dialogue formatted

    def test_format_empty_string(self):
        styler = TextStyler(TelegramHTMLBackend())
        assert styler.format("") == ""

    def test_format_text_with_html_entities_escaped(self):
        styler = TextStyler(TelegramHTMLBackend())
        text = "The temperature dropped & the wind howled < the mountains."
        formatted_text = styler.format(text)
        assert "&amp;" in formatted_text
        assert "&lt;" in formatted_text
        # No raw & or < outside of HTML tags
        # Remove tags, then check
        import re

        stripped = re.sub(r"<[^>]+>", "", formatted_text)
        assert "<" not in stripped
        assert "&" not in stripped or "&amp;" in formatted_text

    def test_format_preserves_newlines(self):
        styler = TextStyler(TelegramHTMLBackend())
        text = "First paragraph.\n\nSecond paragraph."
        formatted_text = styler.format(text)
        assert "\n" in formatted_text


class TestFormatPlain:
    def test_format_plain_returns_readable_text(self):
        styler = TextStyler(PlainTextBackend())
        text = 'Marcus says: "Hello, friend."'
        formatted_text = styler.format(text)
        # Plain backend should return text that is still readable
        assert "Marcus" in formatted_text
        assert "Hello, friend." in formatted_text


# ── Phase 4: Edge cases ──────────────────────────────────────────────


class TestEdgeCases:
    def test_nested_quotes(self):
        """Inner single quotes inside double quotes should not break parsing."""
        styler = TextStyler(TelegramHTMLBackend())
        text = """She said, "He told me 'run!' and I listened." """  # noqa: WPS322
        formatted_text = styler.format(text)
        # Should still detect the outer dialogue
        assert "<i>" in formatted_text

    def test_non_english_quotes(self):
        """Unicode quote marks (Russian guillemets, French quotes) should be detected."""
        styler = TextStyler(TelegramHTMLBackend())
        # Russian-style quotes
        text = "Marcus says: \u00abHello, friend.\u00bb"
        formatted_text = styler.format(text)
        assert "<b>Marcus</b>" in formatted_text
        assert "<i>" in formatted_text

    def test_multiline_dialogue(self):
        """Dialogue that spans a line break within quotes."""
        styler = TextStyler(TelegramHTMLBackend())
        text = 'Marcus says: "I have traveled\nfar and wide."'
        formatted_text = styler.format(text)
        assert "<i>" in formatted_text

    def test_no_false_positive_on_regular_quotes(self):
        """Quotes used for emphasis, not dialogue, shouldn't get NPC_NAME."""
        styler = TextStyler(PlainTextBackend())
        text = 'The sign reads "Beware of the dog" in faded letters.'
        segments = styler.parse(text)
        types = [seg.segment_type for seg in segments]
        # Should have DIALOGUE (quoted text) but NOT NPC_NAME
        assert SegmentType.NPC_NAME not in types
        assert SegmentType.DIALOGUE in types

    def test_text_with_only_separator(self):
        styler = TextStyler(TelegramHTMLBackend())
        formatted_text = styler.format("---")
        assert len(formatted_text.strip()) > 0
