"""Tests for the Actor prompt template including physical_status."""

from __future__ import annotations

import allure

from prompts.actor_prompts import ACTOR_SYSTEM, ACTOR_SYSTEM_ACTION, get_actor_prompts
from prompts.actor_prompts_ru import ACTOR_SYSTEM_ACTION_RU

_DEFAULT_RENDER_VARS = dict(
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


def _render_actor_prompt(**overrides) -> str:
    """Render ACTOR_SYSTEM with sensible defaults, applying overrides."""
    defaults = dict(_DEFAULT_RENDER_VARS)
    defaults.update(overrides)
    return ACTOR_SYSTEM.render(**defaults)


def _render_action_prompt(**overrides) -> str:
    """Render ACTOR_SYSTEM_ACTION with sensible defaults, applying overrides."""
    defaults = dict(_DEFAULT_RENDER_VARS)
    defaults.update(overrides)
    return ACTOR_SYSTEM_ACTION.render(**defaults)


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


@allure.epic("NPC Interaction")
@allure.feature("Actor action-mode prompt template")
class TestActorSystemActionStructure:
    """The NPC autonomous-turn branch uses a dedicated template whose
    constraints section replaces dialogue output rules with a
    JSON-object directive. Character context (identity, biography,
    knowledge, memory, hostility, inventory) is reused verbatim.
    """

    @allure.story("Action-mode required vars")
    @allure.title("ACTOR_SYSTEM_ACTION declares the same character-context required vars as the dialogue template")
    def test_action_required_vars_match_character_context(self):
        shared_vars = {
            "npc_name",
            "npc_occupation",
            "location_name",
            "npc_biography",
            "personality_traits",
            "speech_style",
            "npc_appearance",
            "npc_inventory",
            "accessible_knowledge",
            "current_mood",
            "physical_status",
            "language",
        }
        assert shared_vars.issubset(ACTOR_SYSTEM_ACTION.required_vars)

    @allure.story("Action-mode output directive")
    @allure.title("ACTOR_SYSTEM_ACTION instructs the LLM to return only a JSON object — no fences, no tags")
    def test_action_prompt_instructs_json_only(self):
        rendered = _render_action_prompt()
        lowered = rendered.lower()
        assert "json object" in lowered
        assert "no markdown fences" in lowered

    @allure.story("Action-mode output directive")
    @allure.title("ACTOR_SYSTEM_ACTION omits the dialogue-only output rules from ACTOR_SYSTEM")
    def test_action_prompt_omits_dialogue_rules(self):
        rendered = _render_action_prompt()
        assert "Output ONLY your spoken dialogue" not in rendered
        assert "[MOOD:" not in rendered
        assert "[STATUS:" not in rendered
        assert "[REVEALED:" not in rendered
        assert "[DICE ROLL]" not in rendered

    @allure.story("Action-mode character context")
    @allure.title("ACTOR_SYSTEM_ACTION still carries biography, personality, knowledge, and inventory")
    def test_action_prompt_preserves_character_context(self):
        rendered = _render_action_prompt(
            npc_biography="A disgraced legionary plotting revenge.",
            personality_traits="vengeful, calculating",
            accessible_knowledge="Your brother was ruined by Marcus the merchant.",
            npc_inventory="concealed pugio",
        )
        assert "A disgraced legionary plotting revenge." in rendered
        assert "vengeful, calculating" in rendered
        assert "Your brother was ruined by Marcus the merchant." in rendered
        assert "concealed pugio" in rendered

    @allure.story("Action-mode character context")
    @allure.title("ACTOR_SYSTEM_ACTION preserves the physical-action rule — attacked NPCs act, not just speak")
    def test_action_prompt_preserves_physical_action_rule(self):
        rendered = _render_action_prompt()
        assert "actions, not just words" in rendered.lower()

    @allure.story("Locale catalog")
    @allure.title("get_actor_prompts exposes ``system_action`` for both English and Russian locales")
    def test_catalog_exposes_system_action_per_locale(self):
        assert get_actor_prompts("English").system_action is ACTOR_SYSTEM_ACTION
        assert get_actor_prompts("Russian").system_action is ACTOR_SYSTEM_ACTION_RU

    @allure.story("Locale catalog")
    @allure.title("Unknown locales fall back to the English action template")
    def test_unknown_locale_falls_back_to_english_action(self):
        assert get_actor_prompts("Klingon").system_action is ACTOR_SYSTEM_ACTION
        assert get_actor_prompts(None).system_action is ACTOR_SYSTEM_ACTION

    @allure.story("Locale catalog")
    @allure.title("Russian action template exposes the same required vars as the English action template")
    def test_ru_action_required_vars_match_en(self):
        assert ACTOR_SYSTEM_ACTION_RU.required_vars == ACTOR_SYSTEM_ACTION.required_vars

    @allure.story("Locale catalog")
    @allure.title("Russian action template exposes the same section names as the English action template")
    def test_ru_action_section_names_match_en(self):
        en_names = [section.name for section in ACTOR_SYSTEM_ACTION.sections]
        ru_names = [section.name for section in ACTOR_SYSTEM_ACTION_RU.sections]
        assert en_names == ru_names
