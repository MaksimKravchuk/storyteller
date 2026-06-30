"""Tests for Director setting worldview prompt rendering."""

from __future__ import annotations

import allure

from prompts.director_prompts import DIRECTOR_SYSTEM
from prompts.director_prompts_ru import DIRECTOR_SYSTEM_RU

pytestmark = [allure.epic("NPC Interaction"), allure.feature("Director prompt context")]


@allure.story("Setting worldview context")
@allure.title("Director English prompt renders technologies and social structure beside time period")
def test_director_english_prompt_renders_setting_worldview_vars() -> None:
    rendered = DIRECTOR_SYSTEM.render(
        setting_name="Rome",
        time_period="1 AD",
        setting_technologies="aqueducts, wax tablets",
        social_structure="senators, equites, plebs, freedmen, and enslaved people",
        player_appearance="grey hoodie",
        player_inventory="phone",
        scene_description="Forum",
        npcs_present="None",
        points_of_interest="None",
        game_time="morning",
        game_clock="6.0",
        language="English",
    )

    assert "Time period: 1 AD" in rendered
    assert "Technologies: aqueducts, wax tablets" in rendered
    assert "Social structure: senators, equites, plebs, freedmen, and enslaved people" in rendered


@allure.story("Setting worldview context")
@allure.title("Director Russian prompt renders technologies and social structure beside time period")
def test_director_russian_prompt_renders_setting_worldview_vars() -> None:
    rendered = DIRECTOR_SYSTEM_RU.render(
        setting_name="Рим",
        time_period="1 век н.э.",
        setting_technologies="акведуки, восковые таблички",
        social_structure="сенаторы, всадники, плебеи, вольноотпущенники и рабы",
        player_appearance="серый плащ",
        player_inventory="телефон",
        scene_description="Форум",
        npcs_present="Нет",
        points_of_interest="Нет",
        game_time="утро",
        game_clock="6.0",
        language="Russian",
    )

    assert "Период: 1 век н.э." in rendered
    assert "Технологии: акведуки, восковые таблички" in rendered
    assert "Социальная структура: сенаторы, всадники, плебеи, вольноотпущенники и рабы" in rendered
