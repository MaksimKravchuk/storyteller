"""Tests for the prompt localization system.

Covers:

* :func:`prompts.locales.resolve_locale` — alias normalisation and
  fallback behaviour.
* :func:`prompts.narrator_prompts.get_narrator_prompts` — catalog
  lookup per locale.
* :class:`cast.narrator_labels.NarratorLabels` — locale-specific
  connector strings.
* :class:`cast.narrator.Narrator` — the Russian locale actually flows
  all the way into the rendered system prompt and raw-material labels.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast import narrator as narrator_mod, narrator_labels as narrator_labels_mod
from cast.director_routing import ActionRouter
from cast.schemas.turn_outputs import DialogueEntry, TurnOutputs
from knowledge.graph import KnowledgeGraph
from models import game_state as gs_mod, scene as scene_mod, setting as setting_mod
from prompts import (
    actor_prompts,
    chronicler_prompts,
    data_miner_prompts,
    director_prompts,
    dramaturge_prompts,
)
from prompts import (
    item_generator_prompts,
    narrator_prompts,
    npc_generator_prompts,
    scene_builder_prompts,
)
from prompts.locales import DEFAULT_LOCALE, Locale, resolve_locale

get_actor_prompts = actor_prompts.get_actor_prompts
get_chronicler_prompts = chronicler_prompts.get_chronicler_prompts
get_data_miner_prompts = data_miner_prompts.get_data_miner_prompts
get_director_prompts = director_prompts.get_director_prompts
get_dramaturge_prompts = dramaturge_prompts.get_dramaturge_prompts
get_item_generator_prompts = item_generator_prompts.get_item_generator_prompts
get_narrator_prompts = narrator_prompts.get_narrator_prompts
get_npc_generator_prompts = npc_generator_prompts.get_npc_generator_prompts
get_scene_builder_prompts = scene_builder_prompts.get_scene_builder_prompts

_MESSAGES = "messages"


def _make_game_state() -> gs_mod.GameState:
    """Build a minimal game state for Narrator tests."""
    setting = setting_mod.Setting(
        name="Санкт-Петербург",
        time_period="1703 год",
        region="Россия",
        summary="Основание Петербурга.",
    )
    gs = gs_mod.GameState(setting=setting, knowledge_graph=KnowledgeGraph())
    gs.current_scene = scene_mod.Scene(
        location_id="neva_delta",
        description="Туманная Нева на рассвете.",
        npcs_present=[scene_mod.SceneNPC(role="часовой", uuid="npc-1")],
        points_of_interest=[scene_mod.PointOfInterest(names=["деревянный помост"])],
        ambient_description="Сырой воздух и запах смолы.",
    )
    return gs


def _make_narrator(language: str) -> narrator_mod.Narrator:
    llm_client = AsyncMock()
    llm_client.send_message = AsyncMock(
        return_value=AsyncMock(
            body="Narrated text.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
    )
    return narrator_mod.Narrator(llm_client=llm_client, language=language)


def _system_prompt(narrator: narrator_mod.Narrator) -> str:
    """Return the system prompt most recently sent through the mock LLM."""
    call_kwargs = narrator.llm_client.send_message.call_args.kwargs  # type: ignore[attr-defined]
    return call_kwargs["system_prompt"]


def _last_user_message(narrator: narrator_mod.Narrator) -> str:
    call_kwargs = narrator.llm_client.send_message.call_args.kwargs  # type: ignore[attr-defined]
    return call_kwargs[_MESSAGES][-1].body


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestResolveLocale:
    @allure.story("Locale normalisation")
    @allure.title("resolve_locale maps common English aliases onto Locale.ENGLISH")
    @pytest.mark.parametrize("alias", ["English", "english", "EN", " eng ", "en"])
    def test_resolve_english_aliases(self, alias: str) -> None:
        assert resolve_locale(alias) is Locale.ENGLISH

    @allure.story("Locale normalisation")
    @allure.title("resolve_locale maps common Russian aliases onto Locale.RUSSIAN")
    @pytest.mark.parametrize(
        "alias",
        ["Russian", "russian", "RU", "rus", "русский", "Русский", "русский язык"],
    )
    def test_resolve_russian_aliases(self, alias: str) -> None:
        assert resolve_locale(alias) is Locale.RUSSIAN

    @allure.story("Locale normalisation")
    @allure.title("resolve_locale falls back to DEFAULT_LOCALE for unknown or empty values")
    @pytest.mark.parametrize("value", ["", None, "Klingon", "français"])
    def test_resolve_fallback(self, value) -> None:
        assert resolve_locale(value) is DEFAULT_LOCALE


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestNarratorPromptCatalog:
    @allure.story("Catalog lookup")
    @allure.title("get_narrator_prompts returns distinct bundles for English vs. Russian")
    def test_english_and_russian_bundles_differ(self) -> None:
        english = get_narrator_prompts("English")
        russian = get_narrator_prompts("Russian")
        assert english is not russian
        assert english.system is not russian.system
        assert english.narrate is not russian.narrate

    @allure.story("Catalog lookup")
    @allure.title("Russian Narrator system prompt renders in Russian")
    def test_russian_system_prompt_is_russian(self) -> None:
        rendered = get_narrator_prompts("Russian").system.render(
            setting_name="Санкт-Петербург",
            time_period="1703 год",
            time_of_day="ночь",
            language="русском",
            world_mood="Туман над водой",
        )
        assert "Рассказчик" in rendered
        assert "Санкт-Петербург" in rendered
        assert "Время суток: ночь" in rendered
        assert "Весь текст пиши на языке: русском." in rendered
        # Must NOT contain the English source strings
        assert "Narrator" not in rendered
        assert "Write all your output in" not in rendered

    @allure.story("Catalog lookup")
    @allure.title("Russian Narrator narrate prompt renders in Russian")
    def test_russian_narrate_prompt_is_russian(self) -> None:
        rendered = get_narrator_prompts("Russian").narrate.render(
            player_action="осмотреться",
            raw_material="Сцена: туман на реке.",
            scene_type="NEW_SCENE",
        )
        assert "Действие игрока" in rendered
        assert "Тип сцены: NEW_SCENE" in rendered
        assert "Player action" not in rendered


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestNarratorLabels:
    @allure.story("Connector strings")
    @allure.title("Russian and English narrator labels are distinct")
    def test_labels_differ_per_locale(self) -> None:
        english = narrator_labels_mod.get_narrator_labels("English")
        russian = narrator_labels_mod.get_narrator_labels("Russian")
        assert english.scene != russian.scene
        assert russian.scene.startswith("Сцена:")
        assert english.atmosphere != russian.atmosphere
        assert russian.atmosphere.startswith("Атмосфера:")

    @allure.story("Connector strings")
    @allure.title("Unknown language falls back to English labels")
    def test_unknown_language_falls_back(self) -> None:
        fallback = narrator_labels_mod.get_narrator_labels("Esperanto")
        english = narrator_labels_mod.get_narrator_labels("English")
        assert fallback is english


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestNarratorEndToEndRussian:
    @allure.story("End-to-end")
    @allure.title("Narrator(language='Russian') sends a Russian system prompt to the LLM")
    @pytest.mark.asyncio
    async def test_system_prompt_is_russian(self) -> None:
        narrator = _make_narrator("Russian")
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(scene=gs.current_scene),
            context={"player_action": "осмотреться", "game_state": gs},
        )

        system_prompt = _system_prompt(narrator)
        assert "Рассказчик" in system_prompt
        assert "Весь текст пиши на языке: Russian." in system_prompt
        assert "You are the Narrator" not in system_prompt

    @allure.story("End-to-end")
    @allure.title("Russian Narrator renders scene raw-material with Russian connector labels")
    @pytest.mark.asyncio
    async def test_russian_raw_material_uses_russian_labels(self) -> None:
        narrator = _make_narrator("Russian")
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(scene=gs.current_scene),
            context={"player_action": "осмотреться", "game_state": gs},
        )

        user_msg = _last_user_message(narrator)
        assert "Сцена: Туманная Нева на рассвете." in user_msg
        assert "Атмосфера: Сырой воздух и запах смолы." in user_msg
        # English labels must not leak through
        assert "Scene:" not in user_msg
        assert "Atmosphere:" not in user_msg

    @allure.story("End-to-end")
    @allure.title("Russian Narrator renders dialogue bullets with the Russian 'говорит:' connector")
    @pytest.mark.asyncio
    async def test_russian_dialogue_uses_russian_connector(self) -> None:
        narrator = _make_narrator("Russian")
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(dialogue=[DialogueEntry(npc_name="Часовой", response="Стой!")]),
            context={"player_action": "подойти", "game_state": gs},
        )

        user_msg = _last_user_message(narrator)
        assert "Часовой говорит: Стой!" in user_msg
        assert "says:" not in user_msg


def _assert_distinct_bundles(english_bundle, russian_bundle, template_attrs: list[str]) -> None:
    """Assert EN and RU bundles expose the same templates by name but as distinct objects."""
    assert english_bundle is not russian_bundle
    for attr in template_attrs:
        assert getattr(english_bundle, attr) is not getattr(russian_bundle, attr)


def _assert_section_parity(english_bundle, russian_bundle, template_attrs: list[str]) -> None:
    """Assert each EN/RU template pair has identical section names and required_vars.

    Drop-in replaceability inside the agent is the point of keeping the
    shapes aligned — if this drifts, the agent will call ``set_context``
    with variables one locale needs and the other silently drops.
    """
    for attr in template_attrs:
        english_sections = getattr(english_bundle, attr).sections
        russian_sections = getattr(russian_bundle, attr).sections
        assert len(english_sections) == len(russian_sections)
        for english_section, russian_section in zip(english_sections, russian_sections):
            assert english_section.name == russian_section.name
            assert english_section.required_vars == russian_section.required_vars


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestNPCGeneratorPromptCatalog:
    @allure.story("Catalog lookup")
    @allure.title("get_npc_generator_prompts returns distinct bundles per locale and falls back on unknown")
    def test_bundles_distinct_and_fallback(self) -> None:
        english = get_npc_generator_prompts("English")
        russian = get_npc_generator_prompts("Russian")
        _assert_distinct_bundles(english, russian, ["system", "create"])
        _assert_section_parity(english, russian, ["system", "create"])
        assert get_npc_generator_prompts("Esperanto") is english

    @allure.story("Catalog lookup")
    @allure.title("Russian NPCGenerator prompts render Cyrillic while preserving English enum literals")
    def test_russian_prompts_are_russian_but_enums_english(self) -> None:
        russian = get_npc_generator_prompts("Russian")
        system_rendered = russian.system.render(
            setting_summary="Краткое описание сеттинга",
            location_name="Кузница",
            social_structure="Сословная иерархия",
            language="русском",
        )
        assert "Генератор NPC" in system_rendered
        assert "NPC Generator" not in system_rendered
        create_rendered = russian.create.render(npc_request="кузнец")
        assert "Создай NPC" in create_rendered
        assert "local|city|region|country|world" in create_rendered
        assert '"knowledge_scope"' in create_rendered


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestActorPromptCatalog:
    @allure.story("Catalog lookup")
    @allure.title("get_actor_prompts returns distinct bundles per locale and falls back on unknown")
    def test_bundles_distinct_and_fallback(self) -> None:
        english = get_actor_prompts("English")
        russian = get_actor_prompts("Russian")
        _assert_distinct_bundles(english, russian, ["system"])
        _assert_section_parity(english, russian, ["system"])
        assert get_actor_prompts("Klingon") is english

    @allure.story("Catalog lookup")
    @allure.title("Russian Actor system prompt keeps JSON envelope field names in English")
    def test_machine_parsed_tags_stay_english(self) -> None:
        rendered = get_actor_prompts("Russian").system.render(
            npc_name="Марк",
            npc_occupation="стражник",
            location_name="ворота",
            npc_biography="ветеран легиона",
            personality_traits="суров, скуп на слова",
            speech_style="отрывистый, казарменный",
            npc_appearance="шрам через бровь",
            npc_inventory="меч, щит",
            accessible_knowledge="знает устав",
            current_mood="подозрительное",
            physical_status="здоров",
            language="русском",
        )
        assert '"narration"' in rendered
        assert '"mood"' in rendered
        assert '"status"' in rendered
        assert '"revealed_names"' in rendered
        assert '"self"' in rendered
        # The mood VALUE must also stay English (hostility.py's enum is
        # English-keyed) — a prompt that drops this instruction silently
        # breaks AGGRESSION_THRESHOLDS matching.
        assert '"hostile"' in rendered
        assert "АНГЛИЙСКОЕ" in rendered
        assert "Отвечай на языке: русском." in rendered


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestDramaturgePromptCatalog:
    @allure.story("Catalog lookup")
    @allure.title("get_dramaturge_prompts returns distinct bundles per locale and falls back on unknown")
    def test_bundles_distinct_and_fallback(self) -> None:
        english = get_dramaturge_prompts("English")
        russian = get_dramaturge_prompts("Russian")
        _assert_distinct_bundles(english, russian, ["system", "review"])
        _assert_section_parity(english, russian, ["system", "review"])
        assert get_dramaturge_prompts(None) is english

    @allure.story("Catalog lookup")
    @allure.title("Russian Dramaturge review prompt is Russian and keeps JSON keys English")
    def test_review_prompt_is_russian(self) -> None:
        rendered = get_dramaturge_prompts("Russian").review.render(narration="Туман над Невой.")
        assert "Вывод Рассказчика" in rendered
        assert '"corrected_narration"' in rendered
        assert '"unknown_entities"' in rendered


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestSceneBuilderPromptCatalog:
    @allure.story("Catalog lookup")
    @allure.title("get_scene_builder_prompts returns distinct bundles per locale and falls back on unknown")
    def test_bundles_distinct_and_fallback(self) -> None:
        english = get_scene_builder_prompts("English")
        russian = get_scene_builder_prompts("Russian")
        _assert_distinct_bundles(english, russian, ["system", "generate"])
        _assert_section_parity(english, russian, ["system", "generate"])
        assert get_scene_builder_prompts("Klingon") is english

    @allure.story("Catalog lookup")
    @allure.title("Russian Scene Builder prompt renders Cyrillic with English JSON keys")
    def test_prompt_is_russian(self) -> None:
        rendered = get_scene_builder_prompts("Russian").generate.render(
            player_action="осмотреться",
            time_of_day="утро",
        )
        assert "Сгенерируй сцену" in rendered
        assert '"npcs_present"' in rendered
        assert '"points_of_interest"' in rendered


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestItemGeneratorPromptCatalog:
    @allure.story("Catalog lookup")
    @allure.title("get_item_generator_prompts returns distinct bundles per locale and falls back on unknown")
    def test_bundles_distinct_and_fallback(self) -> None:
        english = get_item_generator_prompts("English")
        russian = get_item_generator_prompts("Russian")
        attrs = ["system", "batch", "examine", "interact"]
        _assert_distinct_bundles(english, russian, attrs)
        _assert_section_parity(english, russian, attrs)
        assert get_item_generator_prompts("Esperanto") is english

    @allure.story("Catalog lookup")
    @allure.title("Russian Item Generator examine prompt is Russian with English JSON keys")
    def test_examine_prompt_is_russian(self) -> None:
        rendered = get_item_generator_prompts("Russian").examine.render(
            item_name="меч",
            context_hint="на столе",
        )
        assert "физический осмотр" in rendered
        assert '"description"' in rendered


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestWorldChroniclerPromptCatalog:
    @allure.story("Catalog lookup")
    @allure.title("get_chronicler_prompts returns distinct bundles per locale and falls back on unknown")
    def test_bundles_distinct_and_fallback(self) -> None:
        english = get_chronicler_prompts("English")
        russian = get_chronicler_prompts("Russian")
        _assert_distinct_bundles(english, russian, ["system", "advance"])
        _assert_section_parity(english, russian, ["system", "advance"])
        assert get_chronicler_prompts("Klingon") is english

    @allure.story("Catalog lookup")
    @allure.title("Russian Chronicler advance prompt preserves category / status / scope enum values in English")
    def test_enum_values_stay_english(self) -> None:
        rendered = get_chronicler_prompts("Russian").advance.render(
            scene_number="5",
            open_threads="(нет открытых нитей)",
            turn_summary="Игрок осмотрелся.",
        )
        assert "personal|political|natural|economic|social|cultural" in rendered
        assert "open|resolved|abandoned" in rendered
        assert "local|remote" in rendered
        assert "Двигай живой мир" in rendered


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestDataMinerPromptCatalog:
    @allure.story("Catalog lookup")
    @allure.title("get_data_miner_prompts returns distinct bundles per locale and falls back on unknown")
    def test_bundles_distinct_and_fallback(self) -> None:
        english = get_data_miner_prompts("English")
        russian = get_data_miner_prompts("Russian")
        attrs = ["system", "search_terms", "research"]
        _assert_distinct_bundles(english, russian, attrs)
        _assert_section_parity(english, russian, attrs)
        assert get_data_miner_prompts("Klingon") is english

    @allure.story("Catalog lookup")
    @allure.title("Russian Data Miner search-terms prompt keeps JSON key 'search_terms' in English")
    def test_search_terms_key_english(self) -> None:
        rendered = get_data_miner_prompts("Russian").search_terms.render(
            setting_request="Флоренция эпохи Медичи",
        )
        assert '"search_terms"' in rendered
        assert "Игрок хочет игровой сеттинг" in rendered


@allure.epic("Narrative Delivery")
@allure.feature("Prompt localization")
class TestDirectorPromptCatalog:
    @allure.story("Catalog lookup")
    @allure.title("get_director_prompts returns distinct bundles per locale and falls back on unknown")
    def test_bundles_distinct_and_fallback(self) -> None:
        english = get_director_prompts("English")
        russian = get_director_prompts("Russian")
        _assert_distinct_bundles(english, russian, ["system", "action_routing"])
        _assert_section_parity(english, russian, ["system", "action_routing"])
        assert get_director_prompts("Klingon") is english

    @allure.story("Catalog lookup")
    @allure.title("Russian Director routing prompt keeps action_type enum values in English")
    def test_action_type_values_stay_english(self) -> None:
        rendered = get_director_prompts("Russian").action_routing.render(
            player_action="пойти на рынок",
        )
        assert "EXPLORE|TALK|INTERACT|EXAMINE|MOVE|SLEEP|WAIT|OTHER" in rendered
        assert "combat|persuasion|deception|intimidation|stealth" in rendered
        assert "Действие игрока" in rendered

    @allure.story("End-to-end")
    @allure.title("ActionRouter threads the Russian routing template into the LLM call")
    @pytest.mark.asyncio
    async def test_action_router_sends_russian_template_to_llm(self) -> None:
        """Integration-layer guard for the Director action-routing path.

        The routing template is stored on a separate ``ActionRouter`` (not on the Director's
        ``BasePerformer`` context), so a bundle regression here would be invisible to the
        template-level catalog tests above.
        """
        gs = _make_game_state()
        send_json = AsyncMock(return_value={"action_type": "EXPLORE"})
        router = ActionRouter(gs, send_json, get_director_prompts("Russian").action_routing)
        await router.route_action("осмотреться вокруг")
        assert send_json.await_args is not None
        prompt_sent = send_json.await_args.args[0]
        assert "EXPLORE|TALK|INTERACT|EXAMINE|MOVE|SLEEP|WAIT|OTHER" in prompt_sent
        assert "Действие игрока" in prompt_sent
        assert "Player action" not in prompt_sent
