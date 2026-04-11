"""Tests for the Actor prompt template including physical_status."""

from __future__ import annotations

import allure

from prompts.actor_prompts import ACTOR_SYSTEM


def _render_actor_prompt(**overrides) -> str:
    """Render ACTOR_SYSTEM with sensible defaults, applying overrides."""
    defaults = dict(
        npc_name="Guard",
        npc_occupation="city guard",
        location_name="forum",
        npc_biography="A loyal soldier.",
        personality_traits="brave, stern",
        speech_style="curt",
        npc_appearance="tall, armored",
        npc_inventory="spear, shield",
        accessible_knowledge="The forum closes at dusk.",
        current_mood="neutral",
        physical_status="healthy",
        language="English",
    )
    defaults.update(overrides)
    return ACTOR_SYSTEM.render(**defaults)


@allure.epic("NPC Interaction")
@allure.feature("Actor prompt template")
class TestActorPromptPhysicalStatus:
    @allure.story("Physical status tag")
    @allure.title("Actor prompt template declares physical_status as a required variable")
    def test_physical_status_in_required_vars(self):
        assert "physical_status" in ACTOR_SYSTEM.required_vars

    @allure.story("Physical status tag")
    @allure.title("Actor prompt interpolates the NPC's physical status into the rendered system prompt")
    def test_prompt_contains_physical_status(self):
        rendered = _render_actor_prompt(physical_status="wounded left arm")
        assert "wounded left arm" in rendered

    @allure.story("Physical status tag")
    @allure.title("Actor prompt tells the NPC to emit a [STATUS:] tag so changes can be parsed")
    def test_prompt_contains_status_tag_instruction(self):
        rendered = _render_actor_prompt()
        assert "[STATUS:" in rendered

    @allure.story("Behavioral rules")
    @allure.title("Actor prompt instructs NPCs to go unconscious when their status reaches that threshold")
    def test_prompt_contains_behavioral_rule(self):
        rendered = _render_actor_prompt()
        assert "unconscious" in rendered.lower()
