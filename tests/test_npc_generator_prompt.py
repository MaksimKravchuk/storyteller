"""Regression tests for the NPC generator prompt template.

Guards KER-22: the ``speech_style`` instruction must push the LLM toward
style descriptors (register, vocabulary, rhythm, emotional control) and
explicitly forbid verbatim example phrases or catchphrases that the
Actor would later echo every turn.
"""

from __future__ import annotations

import allure

from prompts.npc_generator_prompts import NPC_GENERATOR_CREATE


def _render_create_prompt() -> str:
    return NPC_GENERATOR_CREATE.render(npc_request="city guard")


@allure.epic("NPC Interaction")
@allure.feature("NPC Generator prompt template")
class TestNPCGeneratorSpeechStyleInstruction:
    @allure.story("Speech style descriptors")
    @allure.title("NPC generator asks for style descriptors, not generated dialogue")
    def test_asks_for_style_descriptors(self) -> None:
        rendered = _render_create_prompt().lower()
        assert "register" in rendered
        assert "vocabulary" in rendered
        # Rhythm and emotional control round out the descriptor set.
        assert "rhythm" in rendered
        assert "emotional control" in rendered

    @allure.story("Speech style descriptors")
    @allure.title("NPC generator forbids verbatim example phrases in speech_style")
    def test_forbids_verbatim_example_phrases(self) -> None:
        rendered = _render_create_prompt().lower()
        assert "verbatim" in rendered
        assert "catchphrase" in rendered

    @allure.story("Speech style descriptors")
    @allure.title("NPC generator frames speech_style as HOW they speak, never WHAT they say")
    def test_frames_how_not_what(self) -> None:
        rendered = _render_create_prompt()
        assert "HOW they speak" in rendered
        assert "never WHAT they say" in rendered


@allure.epic("NPC Interaction")
@allure.feature("NPC Generator prompt template")
class TestNPCGeneratorShortDescriptorInstruction:
    """Guards KER-28: the prompt must elicit a glance-level visible-features
    phrase that is safe to surface before the player has been introduced.
    """

    @allure.story("Short descriptor")
    @allure.title("NPC generator requests a short_descriptor field in the JSON contract")
    def test_declares_short_descriptor_field(self) -> None:
        assert '"short_descriptor"' in _render_create_prompt()

    @allure.story("Short descriptor")
    @allure.title("NPC generator caps short_descriptor at 80 chars and forbids name or occupation")
    def test_constrains_short_descriptor_content(self) -> None:
        rendered = _render_create_prompt()
        assert "≤80 chars" in rendered
        assert "name or occupation" in rendered.lower()
