"""Russian-locale prompt templates for the Data Miner agent.

Mirrors :mod:`prompts.data_miner_prompts`. JSON keys stay in English
because :class:`cast.schemas.setting_response.SettingResponse` expects
them verbatim. Wikipedia search terms themselves stay in whatever form
the LLM finds most productive — we query English Wikipedia from this
repo, so Latin / English entity names are still preferred for
``search_terms`` even when the session language is Russian. Only
human-readable field values in the ``SettingResponse`` (name, summary,
description, traditions, social_structure) translate.
"""

from prompts.base_template import PromptSection, PromptTemplate

DATA_MINER_SYSTEM_RU = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "Ты — специалист по исторической разведке для интерактивного "
                "текстового квеста. Твоя задача — синтезировать сырые выдержки "
                "из Википедии в структурированный игровой сеттинг. Сохраняй "
                "достоверность реальной истории, но заполняй правдоподобные "
                "детали там, где источники скупы."
            ),
        ),
        PromptSection(
            name="language",
            template=(
                "Все человекочитаемые поля вывода (name, time_period, region, "
                "summary, role, description, traditions, social_structure) пиши "
                "на языке: {language}. Ключи JSON оставляй на английском — они "
                "читаются кодом. Поисковые термины для Википедии (search_terms) "
                "оставляй в том виде, в каком статьи реально существуют в "
                "английской Википедии — обычно это английские/латинские названия."
            ),
            required_vars=["language"],
        ),
    ]
)


DATA_MINER_SEARCH_TERMS_RU = (
    "Игрок хочет игровой сеттинг на основе:\n"
    '"{setting_request}"\n\n'
    "Сформируй JSON-список из 3-8 поисковых терминов Википедии, "
    "которые дадут нам лучший исторический контекст для этого "
    "сеттинга. Термины оставляй в том виде, в каком статьи "
    "существуют в английской Википедии.\n"
    "Выведи ТОЛЬКО JSON-объект: "
    '{{"search_terms": ["term1", "term2", ...]}}'
)


DATA_MINER_RESEARCH_RU = (
    "Запрос сеттинга: {setting_request}\n\n"
    "Сырая выдержка из Википедии:\n{raw_research}\n\n"
    "Синтезируй это в структурированный игровой сеттинг. "
    "Выведи ТОЛЬКО валидный JSON со следующими полями:\n"
    "{{\n"
    '  "name": "Название сеттинга",\n'
    '  "time_period": "например, 1 век н.э.",\n'
    '  "region": "например, Римская империя, Италия",\n'
    '  "summary": "Обзор в 2-3 абзаца",\n'
    '  "key_persons": [{{"name": "...", "role": "...", "description": "..."}}],\n'
    '  "key_events": [{{"name": "...", "date": "...", "description": "..."}}],\n'
    '  "locations": [{{"name": "...", "type": "...", "description": "..."}}],\n'
    '  "traditions": ["..."],\n'
    '  "technologies": ["..."],\n'
    '  "social_structure": "Описание социальной иерархии"\n'
    "}}"
)
