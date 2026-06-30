"""Russian-locale prompt template for the anachronism classifier substrate."""

from __future__ import annotations

from prompts.base_template import PromptSection, PromptTemplate

ANACHRONISM_CLASSIFIER_SYSTEM_RU = PromptTemplate(
    [
        PromptSection(
            name="worldview",
            template=(
                "МИРОВОЗЗРЕНИЕ\n"
                "Персонаж игрока происходит из эпохи: {origin_era}. Оценивай, что покажется "
                "людям текущего сеттинга незнакомым, магическим, невозможным, табуированным "
                "или социально непонятным. Не блокируй действие игрока; только классифицируй "
                "воспринимаемую странность."
            ),
            required_vars=["origin_era"],
        ),
        PromptSection(
            name="setting",
            template=(
                "СЕТТИНГ\n"
                "Мир: {setting_name}\n"
                "Период: {time_period}\n"
                "Технологии: {setting_technologies}\n"
                "Социальная структура: {social_structure}"
            ),
            required_vars=["setting_name", "time_period", "setting_technologies", "social_structure"],
        ),
        PromptSection(
            name="action",
            template=(
                "ДЕЙСТВИЕ\n"
                "Сравни действие игрока с мировоззрением сеттинга. Когда подходит, используй "
                "эти seed-идентификаторы вместо близких синонимов: {seed_concepts}. Если seed "
                "не подходит, добавь краткий snake_case идентификатор. Верни score 0 и пустые "
                "списки/текст, когда действие не содержит значимого анахронизма или незнакомого понятия."
            ),
            required_vars=["seed_concepts"],
        ),
    ]
)

ANACHRONISM_CLASSIFIER_REVIEW_RU = (
    'Действие игрока: "{player_action}"\n\n'
    "Классифицируй только понятия, которые люди сеттинга воспримут как незнакомые. Верни ТОЛЬКО "
    "валидный JSON по этой схеме:\n"
    "{{\n"
    '  "strangeness_score": 0,\n'
    '  "unfamiliar_concepts": ["canonical_snake_case_identifier"],\n'
    '  "perceived_rewrite": "краткое описание странного действия с точки зрения мира"\n'
    "}}"
)
