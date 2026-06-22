"""Tests for the Actor prompt template including physical_status."""

from __future__ import annotations

import allure

from cast.actor_config import goal_prompt_vars
from models.goal import Goal, GoalKind
from models.npc_card import NPCCard
from prompts.actor_prompts import ACTOR_SYSTEM_ACTION, ACTOR_SYSTEM_DIALOGUE
from prompts.actor_prompts_ru import ACTOR_SYSTEM_DIALOGUE_RU
from tests.actor_helpers import BASE_ACTOR_PROMPT_VARS, render_actor_system


def _section_template(template, name: str) -> str:
    return next(section.template for section in template._sections if section.name == name)


def _section_required_vars(template, name: str) -> list[str]:
    return next(section.required_vars for section in template._sections if section.name == name)


@allure.epic("NPC Interaction")
@allure.feature("Actor prompt template")
class TestActorPromptPhysicalStatus:
    @allure.story("Physical status tag")
    @allure.title("Actor prompt template declares physical_status as a required variable")
    def test_physical_status_in_required_vars(self):
        assert "physical_status" in ACTOR_SYSTEM_DIALOGUE.required_vars

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
class TestActorPromptMemorySection:
    @allure.story("Memory section")
    @allure.title("Actor memory section keeps the same required var in English and Russian")
    def test_memory_section_required_vars_remain_past_memories(self):
        assert _section_required_vars(ACTOR_SYSTEM_DIALOGUE, "memory") == ["past_memories"]
        assert _section_required_vars(ACTOR_SYSTEM_DIALOGUE_RU, "memory") == ["past_memories"]

    @allure.story("Memory section")
    @allure.title("Actor memory section describes memories as relevant recall, not only past interaction")
    def test_memory_section_wording_mentions_relevant_memories(self):
        english = _section_template(ACTOR_SYSTEM_DIALOGUE, "memory")
        russian = _section_template(ACTOR_SYSTEM_DIALOGUE_RU, "memory")

        assert "relevant memories you may draw on" in english
        assert "past interactions with this person" not in english
        assert "Релевантные воспоминания, на которые ты можешь опираться" in russian
        assert "прошлом общении с этим человеком" not in russian


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
        assert "1–3 sentences" not in lowered

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
    """The Actor system prompt uses two distinct templates for two output modes.

    Dialogue mode keeps the narration/mood/status/revealed_names envelope.
    Action mode (NPC autonomous turn) emits the action/type/target schema
    instead — the two templates are mutually exclusive so the LLM is never
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
        rendered = ACTOR_SYSTEM_DIALOGUE_RU.render(
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
        assert '"narration"' in rendered
        assert "ATTACK|TALK|MOVE|IDLE|STEALTH|PERSUADE|DECEIVE|INTIMIDATE" not in rendered

    @allure.story("Output mode gating")
    @allure.title("Dialogue and action templates are mutually exclusive — each has exactly one output section")
    def test_dialogue_and_action_templates_are_mutually_exclusive(self):
        dialogue_section_names = {section.name for section in ACTOR_SYSTEM_DIALOGUE._sections}
        action_section_names = {section.name for section in ACTOR_SYSTEM_ACTION._sections}
        assert "output_dialogue" in dialogue_section_names
        assert "output_action" not in dialogue_section_names
        assert "output_action" in action_section_names
        assert "output_dialogue" not in action_section_names

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
            "goal_last_outcome",
        }
        assert goal_vars.issubset(set(ACTOR_SYSTEM_DIALOGUE.required_vars))
        assert goal_vars.issubset(set(ACTOR_SYSTEM_DIALOGUE_RU.required_vars))


@allure.epic("NPC Interaction")
@allure.feature("Actor prompt template")
class TestActorPromptOffSceneOutcome:
    """Consumer seam: an off-scene ``last_outcome`` must reach the Actor prompt body.

    The producer is the background ticker (``cast._npc_offscreen_resolvers``)
    which stamps ``Goal.last_outcome``; the consumer is the rendered Actor
    system prompt. These tests assert the var actually lands in the prompt
    text for non-KILL goals, and is *absent* for KILL so the combat prompt
    stays byte-for-byte unchanged.
    """

    @allure.story("Off-scene outcome")
    @allure.title("A non-KILL goal's last_outcome is interpolated into the rendered Actor prompt")
    def test_non_kill_outcome_reaches_prompt(self):
        npc = NPCCard(
            name="Cassia",
            occupation="thief",
            life_goal=Goal(kind=GoalKind.ACQUIRE, description="the senator's ledger"),
        )
        assert npc.life_goal is not None
        npc.life_goal.last_outcome = "secured the senator's ledger"

        rendered = self._render_with_goal(npc)

        assert "While you were away" in rendered
        assert "secured the senator's ledger" in rendered

    @allure.story("Off-scene outcome")
    @allure.title("A KILL goal renders no off-scene outcome section (combat prompt unchanged)")
    def test_kill_goal_omits_outcome_section(self):
        npc = NPCCard(
            name="Brutus",
            occupation="former legionary",
            life_goal=Goal(kind=GoalKind.KILL, description="Avenge brother by killing Marcus"),
        )

        rendered = self._render_with_goal(npc)

        assert "While you were away" not in rendered

    def _render_with_goal(self, npc: NPCCard) -> str:
        goal_vars = goal_prompt_vars(npc, "Marcus", "English")
        assert goal_vars is not None
        return ACTOR_SYSTEM_DIALOGUE.render(**{**BASE_ACTOR_PROMPT_VARS, **goal_vars})
