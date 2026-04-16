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

from cast.narrator import Narrator
from cast.narrator_labels import get_narrator_labels
from cast.schemas.turn_outputs import DialogueEntry, TurnOutputs
from knowledge.graph import KnowledgeGraph
from models import game_state as gs_mod, scene as scene_mod, setting as setting_mod
from prompts.locales import DEFAULT_LOCALE, Locale, resolve_locale
from prompts.narrator_prompts import get_narrator_prompts

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
        points_of_interest=["деревянный помост"],
        ambient_description="Сырой воздух и запах смолы.",
    )
    return gs


def _make_narrator(language: str) -> Narrator:
    llm_client = AsyncMock()
    llm_client.send_message = AsyncMock(
        return_value=AsyncMock(
            body="Narrated text.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
    )
    return Narrator(llm_client=llm_client, language=language)


def _system_prompt(narrator: Narrator) -> str:
    """Return the system prompt most recently sent through the mock LLM."""
    call_kwargs = narrator.llm_client.send_message.call_args.kwargs  # type: ignore[attr-defined]
    return call_kwargs["system_prompt"]


def _last_user_message(narrator: Narrator) -> str:
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
        english = get_narrator_labels("English")
        russian = get_narrator_labels("Russian")
        assert english.scene != russian.scene
        assert russian.scene.startswith("Сцена:")
        assert english.atmosphere != russian.atmosphere
        assert russian.atmosphere.startswith("Атмосфера:")

    @allure.story("Connector strings")
    @allure.title("Unknown language falls back to English labels")
    def test_unknown_language_falls_back(self) -> None:
        fallback = get_narrator_labels("Esperanto")
        english = get_narrator_labels("English")
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
