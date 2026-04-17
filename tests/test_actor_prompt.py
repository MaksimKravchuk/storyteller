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


@allure.epic("NPC Interaction")
@allure.feature("Actor prompt template")
class TestActorPromptRoleScopedReactions:
    """Regression guard for KER-21: the stimulus-response menu must not enumerate occupations.

    The pre-KER-21 prompt listed "A guard fights back, restrains, or calls for help. A
    merchant flees or screams. A warrior draws steel.", so every NPC — cook, carpenter,
    beggar — saw the full menu and gravitated toward the most dramatic entry. The fixed
    prompt refers to the NPC's own ``{npc_occupation}`` instead.
    """

    @allure.story("Role-scoped combat reactions")
    @allure.title("Actor constraints no longer enumerate guard / merchant / warrior reactions")
    def test_constraints_no_enumerated_role_menu(self):
        rendered = _render_actor_prompt(npc_occupation="cook")
        lowered = rendered.lower()
        assert "guard fights back" not in lowered
        assert "merchant flees" not in lowered
        assert "warrior draws steel" not in lowered

    @allure.story("Role-scoped combat reactions")
    @allure.title("Actor constraints reference the NPC's own occupation so reactions stay in character")
    def test_constraints_reference_own_occupation(self):
        rendered = _render_actor_prompt(npc_occupation="cook")
        # The constraints section should bind the combat reaction to THIS NPC's occupation.
        assert "cook" in rendered

    @allure.story("Role-scoped combat reactions")
    @allure.title("Actor constraints still instruct NPCs to act physically when attacked")
    def test_constraints_preserve_physical_action_rule(self):
        rendered = _render_actor_prompt()
        lowered = rendered.lower()
        assert "attack" in lowered
        assert "actions, not just words" in lowered

    @allure.story("Role-scoped combat reactions")
    @allure.title("Actor constraints still emit DICE ROLL, MOOD, and STATUS tag instructions")
    def test_constraints_preserve_dice_mood_status_rules(self):
        rendered = _render_actor_prompt()
        assert "[DICE ROLL]" in rendered
        assert "[MOOD:" in rendered
        assert "[STATUS:" in rendered


@allure.epic("NPC Interaction")
@allure.feature("Actor prompt template")
class TestActorPromptSituationalRegister:
    """Regression guard for KER-22: the Actor must not clamp every reply to 1-3
    sentences, and must treat ``speech_style`` examples as style cues rather
    than literal catchphrases to echo every turn.
    """

    @allure.story("Situational register")
    @allure.title("Actor constraints no longer impose a hard 1-3 sentence length clamp")
    def test_no_hard_length_clamp(self):
        rendered = _render_actor_prompt()
        lowered = rendered.lower()
        # The old clamp was "Keep responses concise — 1-3 sentences typically."
        assert "1-3 sentences" not in lowered
        assert "1\u20133 sentences" not in lowered

    @allure.story("Situational register")
    @allure.title("Actor constraints tie response length to the situation, not a fixed quota")
    def test_constraints_situational_length_guidance(self):
        rendered = _render_actor_prompt()
        lowered = rendered.lower()
        assert "match response length to the situation" in lowered
        # The guidance distinguishes challenge/shout from conversational exchanges.
        assert "challenge" in lowered
        assert "introduction" in lowered

    @allure.story("Speech style as cues")
    @allure.title("Actor constraints forbid echoing quoted example phrases from speech_style")
    def test_constraints_reject_verbatim_style_echo(self):
        rendered = _render_actor_prompt()
        lowered = rendered.lower()
        assert "style cues" in lowered
        assert "verbatim" in lowered
        assert "paraphrase" in lowered
        assert "catchphrase" in lowered
