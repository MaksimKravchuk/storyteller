"""Tests for the Actor prompt template including physical_status."""

from __future__ import annotations

import allure

from prompts.actor_prompts import ACTOR_SYSTEM
from prompts.actor_prompts_ru import ACTOR_SYSTEM_RU
from tests.actor_helpers import render_actor_system


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
        rendered = render_actor_system(physical_status="wounded left arm")
        assert "wounded left arm" in rendered

    @allure.story("Physical status tag")
    @allure.title("Actor prompt tells the NPC to report status changes via the JSON envelope status field")
    def test_prompt_contains_status_field_instruction(self):
        rendered = render_actor_system()
        assert '"status"' in rendered

    @allure.story("Behavioral rules")
    @allure.title("Actor prompt instructs NPCs to go unconscious when their status reaches that threshold")
    def test_prompt_contains_behavioral_rule(self):
        rendered = render_actor_system()
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
        rendered = render_actor_system(npc_occupation="cook")
        lowered = rendered.lower()
        assert "guard fights back" not in lowered
        assert "merchant flees" not in lowered
        assert "warrior draws steel" not in lowered

    @allure.story("Role-scoped combat reactions")
    @allure.title("Actor constraints reference the NPC's own occupation so reactions stay in character")
    def test_constraints_reference_own_occupation(self):
        rendered = render_actor_system(npc_occupation="cook")
        # The constraints section should bind the combat reaction to THIS NPC's occupation.
        assert "cook" in rendered

    @allure.story("Role-scoped combat reactions")
    @allure.title("Actor constraints still instruct NPCs to act physically when attacked")
    def test_constraints_preserve_physical_action_rule(self):
        rendered = render_actor_system()
        lowered = rendered.lower()
        assert "attack" in lowered
        assert "actions, not just words" in lowered

    @allure.story("Role-scoped combat reactions")
    @allure.title("Actor constraints still emit DICE ROLL instruction and describe the mood/status JSON fields")
    def test_constraints_preserve_dice_mood_status_rules(self):
        rendered = render_actor_system()
        assert "[DICE ROLL]" in rendered
        assert '"mood"' in rendered
        assert '"status"' in rendered


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
        rendered = render_actor_system()
        lowered = rendered.lower()
        # The old clamp was "Keep responses concise — 1-3 sentences typically."
        assert "1-3 sentences" not in lowered
        assert "1\u20133 sentences" not in lowered

    @allure.story("Situational register")
    @allure.title("Actor constraints tie response length to the situation, not a fixed quota")
    def test_constraints_situational_length_guidance(self):
        rendered = render_actor_system()
        lowered = rendered.lower()
        assert "match response length to the situation" in lowered
        # The guidance distinguishes challenge/shout from conversational exchanges.
        assert "challenge" in lowered
        assert "introduction" in lowered

    @allure.story("Speech style as cues")
    @allure.title("Actor constraints forbid echoing quoted example phrases from speech_style")
    def test_constraints_reject_verbatim_style_echo(self):
        rendered = render_actor_system()
        lowered = rendered.lower()
        assert "style cues" in lowered
        assert "verbatim" in lowered
        assert "paraphrase" in lowered
        assert "catchphrase" in lowered


@allure.epic("NPC Interaction")
@allure.feature("Actor prompt template")
class TestActorPromptOutputModes:
    """The Actor system prompt carries mode-gated output rules.

    Dialogue mode keeps the narration/mood/status/revealed_names envelope.
    Action mode (NPC autonomous turn) emits the action/type/target schema
    instead — the two sections are mutually exclusive so the LLM is never
    asked to satisfy both envelopes at once.
    """

    @allure.story("Output mode gating")
    @allure.title("Dialogue mode renders the narration envelope schema and not the action schema")
    def test_dialogue_mode_contains_envelope_schema(self):
        rendered = render_actor_system()
        assert '"narration"' in rendered
        assert '"revealed_names"' in rendered
        assert "ATTACK|TALK|MOVE" not in rendered

    @allure.story("Output mode gating")
    @allure.title("Action mode renders the action/type/target schema and not the narration envelope")
    def test_action_mode_contains_action_schema(self):
        rendered = render_actor_system(mode="action")
        assert "ATTACK|TALK|MOVE|IDLE|STEALTH|PERSUADE|DECEIVE|INTIMIDATE" in rendered
        assert '"action"' in rendered
        assert '"target"' in rendered
        assert '"narration"' not in rendered
        assert '"revealed_names"' not in rendered

    @allure.story("Output mode gating")
    @allure.title("Action mode keeps the shared constraints block (dice, in-character, physical status)")
    def test_action_mode_preserves_common_constraints(self):
        rendered = render_actor_system(mode="action")
        assert "[DICE ROLL]" in rendered
        assert "Stay in character" in rendered
        assert "Your physical status:" in rendered

    @allure.story("Output mode gating")
    @allure.title("Russian catalog mirrors the output-mode split")
    def test_russian_catalog_action_mode(self):
        rendered = render_actor_system(template=ACTOR_SYSTEM_RU, mode="action")
        assert "ATTACK|TALK|MOVE|IDLE|STEALTH|PERSUADE|DECEIVE|INTIMIDATE" in rendered
        assert '"narration"' not in rendered

    @allure.story("Output mode gating")
    @allure.title("Neither output section renders when no output_mode var is set")
    def test_no_output_section_when_mode_unset(self):
        # Defensive assertion: callers always set one gate var, but a
        # forgotten call must degrade to no schema rather than double-rendering.
        rendered = render_actor_system(mode="none")
        assert '"narration"' not in rendered
        assert "ATTACK|TALK|MOVE" not in rendered

    @allure.story("Goal section parity")
    @allure.title("English and Russian Actor templates declare the same goal vars")
    def test_goal_section_parity(self):
        goal_vars = {
            "goal_kind",
            "goal_target",
            "goal_turns_pursued",
            "goal_description",
            "goal_last_action",
            "goal_progress_notes",
        }
        assert goal_vars.issubset(set(ACTOR_SYSTEM.required_vars))
        assert goal_vars.issubset(set(ACTOR_SYSTEM_RU.required_vars))
