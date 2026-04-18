"""Russian-locale prompt templates for the NPC Generator agent.

Mirrors the structure of :mod:`prompts.npc_generator_prompts` (section
names and required variables match exactly) so the two catalogs are
drop-in replacements for each other inside
:class:`cast.npc_generator.NPCGenerator`.

Structured JSON fields (``knowledge_scope`` values, ``attributes`` dict
keys) stay in English because downstream code pattern-matches on the
literal strings. Only human-readable guidance is translated.
"""

from prompts.base_template import PromptSection, PromptTemplate

NPC_GENERATOR_SYSTEM_RU = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "Ты — Генератор NPC для интерактивного текстового квеста. "
                "Ты создаёшь детальные, исторически правдоподобные карточки "
                "персонажей. Каждый NPC должен ощущаться как реальный человек "
                "со своей жизнью, целями и ограничениями — а не как сюжетный "
                "инструмент."
            ),
        ),
        PromptSection(
            name="setting",
            template=("Сеттинг: {setting_summary}\nЛокация: {location_name}\nСоциальная структура: {social_structure}"),
            required_vars=["setting_summary", "location_name", "social_structure"],
        ),
        PromptSection(
            name="language",
            template=(
                "Все текстовые поля (name, biography, appearance, short_descriptor, "
                "occupation, personality_traits, speech_style, inventory) заполняй "
                "на языке: {language}. Ключи JSON и значения-перечисления "
                "(knowledge_scope, ключи attributes) оставляй на английском — они "
                "читаются кодом."
            ),
            required_vars=["language"],
        ),
    ]
)


NPC_GENERATOR_CREATE_RU = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                "Создай NPC: {npc_request}\n\n"
                "Выведи ТОЛЬКО валидный JSON со следующими полями:\n"
                "{{\n"
                '  "name": "Исторически уместное имя",\n'
                '  "biography": "2-3 предложения предыстории",\n'
                '  "appearance": "Внешность, одежда, отличительные черты",\n'
                '  "short_descriptor": "Одна фраза о видимых чертах, которые '
                "незнакомец замечает с первого взгляда (≤80 символов). НЕ должна "
                "содержать имя NPC или название его занятия. "
                "Пример: 'коренастая женщина в окровавленном фартуке'.\",\n"
                '  "occupation": "Его ремесло или роль",\n'
                '  "personality_traits": ["черта1", "черта2", "черта3"],\n'
                '  "speech_style": "Опиши КАК он говорит, а не ЧТО говорит. '
                "Укажи: регистр (формальный/разговорный/грубый), уровень лексики "
                "(учёный/простой/деревенский), ритм речи "
                "(отрывистый/плавный/многословный) и эмоциональный контроль "
                "(сдержанный/взрывной/сухой). НЕ вставляй дословных примеров реплик, "
                'присказок или процитированных фраз, которые он «обычно говорит».",\n'
                '  "knowledge_scope": "local|city|region|country|world",\n'
                '  "attributes": {{\n'
                '    "education": 0-10,\n'
                '    "social_status": 0-10,\n'
                '    "friendliness": 0-10,\n'
                '    "suspicion": 0-10,\n'
                '    "combat_skill": 0-10,    // 0=беспомощен, 3=средний, '
                "7=обученный солдат, 10=мастер клинка\n"
                '    "persuasion_skill": 0-10, // 0=неубедителен, 5=средний, '
                "10=искусный дипломат\n"
                '    "deception_skill": 0-10,  // 0=прозрачен, 5=средний, '
                "10=непревзойдённый лжец\n"
                '    "intimidation_skill": 0-10, // 0=безобиден, 5=средний, '
                "10=устрашающий\n"
                '    "perception_skill": 0-10, // 0=рассеян, 5=средний, '
                "10=ничего не ускользает\n"
                '    "stealth_skill": 0-10     // 0=неуклюж, 5=средний, '
                "10=тень\n"
                "  }},\n"
                '  "inventory": ["предметы, которые он носит или продаёт"]\n'
                "}}"
            ),
            required_vars=["npc_request"],
        ),
        PromptSection(
            name="forbidden_names",
            template=(
                "Следующие имена уже заняты другими персонажами этой сцены — "
                "выбери чётко отличное полное имя (разные имя И фамилия) для "
                "этого NPC:\n{forbidden_names}"
            ),
            required_vars=["forbidden_names"],
        ),
    ]
)
