"""Russian-locale prompt templates for the Actor agent (NPC dialogue).

Mirrors the structure of :mod:`prompts.actor_prompts` (section names
and required variables match exactly) so the two catalogs are drop-in
replacements for each other inside :class:`cast.actor.Actor`.

The JSON envelope field names (narration, mood, status, revealed_names)
must stay English as they are parsed by the ActorEnvelope schema.
The ``mood`` value must be an English word (hostile, enraged, angry …)
because it is matched against the English-keyed enum in
:mod:`cast.hostility`.  ``status`` values and ``revealed_names`` entries
can be in the game language (Russian).
"""

from types import MappingProxyType

from models.goal import OffSceneOutcomeKind
from prompts.base_template import PromptSection, PromptTemplate

# Russian renderings of structured off-scene outcomes. ``{detail}`` is a
# data slot (target name / goal description); kinds without a slot ignore
# it. Keys MUST match the English bank in prompts.actor_prompts.
OFFSCREEN_OUTCOME_TEMPLATES_RU: MappingProxyType[OffSceneOutcomeKind, str] = MappingProxyType(
    {
        OffSceneOutcomeKind.PURSUE_CAUGHT_UP: "настиг(ла) {detail} вне сцены",
        OffSceneOutcomeKind.PURSUE_TRACKING: "всё ещё идёт по следу {detail}",
        OffSceneOutcomeKind.PURSUE_TRACKING_UNKNOWN: "всё ещё выслеживает свою добычу",
        OffSceneOutcomeKind.PURSUE_TARGET_DEAD: "{detail} мёртв — погоня окончена",
        OffSceneOutcomeKind.ACQUIRE_PROGRESS: "продвинулся(лась) к цели: {detail}",
        OffSceneOutcomeKind.ACQUIRE_SECURED: "добыл(а) желаемое: {detail}",
        OffSceneOutcomeKind.REST_RECOVERED: "отдохнул(а) вне сцены и полностью восстановился(лась)",
        OffSceneOutcomeKind.REST_AT_EASE: "отдохнул(а) вне сцены; и так был(а) здоров(а)",
    },
)

_IDENTITY_RU = PromptSection(
    name="identity",
    template=(
        "Ты — {npc_name}, {npc_occupation} в месте под названием {location_name}.\n"
        "Биография: {npc_biography}\n"
        "Характер: {personality_traits}\n"
        "Стиль речи: {speech_style}\n"
        "Внешность: {npc_appearance}"
    ),
    required_vars=[
        "npc_name",
        "npc_occupation",
        "location_name",
        "npc_biography",
        "personality_traits",
        "speech_style",
        "npc_appearance",
    ],
)

_INVENTORY_RU = PromptSection(
    name="inventory",
    template="Твой инвентарь / товары: {npc_inventory}",
    required_vars=["npc_inventory"],
)

_KNOWLEDGE_RU = PromptSection(
    name="knowledge",
    template="Что ты знаешь:\n{accessible_knowledge}",
    required_vars=["accessible_knowledge"],
)

_MEMORY_RU = PromptSection(
    name="memory",
    template=("Релевантные воспоминания, на которые ты можешь опираться:\n{past_memories}"),
    required_vars=["past_memories"],
)

_HOSTILITY_RU = PromptSection(
    name="hostility",
    template=(
        "Ты вовлечён во враждебное столкновение с игроком "
        "(уровень враждебности к нему: {hostility_level}; чем выше, тем "
        "сильнее вовлечение). Не возвращайся к рутинным любезностям или "
        "формальному обращению.\n"
        "Недавние действия игрока против тебя:\n{recent_hostile_actions_summary}"
    ),
    required_vars=["hostility_level", "recent_hostile_actions_summary"],
)

# Goal coaching banks (Russian). Selected by GoalKind category in
# cast.actor_config._goal_coaching and interpolated into _GOAL_RU as
# {goal_coaching}. The hostile bank is the STEALTH→ATTACK escalation that
# used to be hardcoded in _GOAL_RU; the social/avoid banks coach a
# non-violent pursuit so a BEFRIEND/TRADE goal no longer reads as "attack".
GOAL_COACHING_HOSTILE_RU = (
    "Перечитай своё последнее действие: если ты несколько ходов "
    "STEALTH-ишь или занимаешь позицию, а момент открыт (цель одна, "
    "свидетелей в сцене не названо) — переходи в ATTACK. Повтор "
    "STEALTH каждый ход — это провал; меняй приём, отступай или "
    "бей. Бездействие — это тоже выбор, но только когда препятствие "
    "конкретно и названо в твоём описании действия."
)

GOAL_COACHING_SOCIAL_RU = (
    "Добивайся этой цели так, как это сделал бы ИМЕННО твой персонаж: "
    "через разговор, сближение, предложения, услуги или общие мгновения — "
    "не силой. Перечитай своё последнее действие: повторять один и тот же "
    "заход каждый ход — это провал; меняй подход, смени тему или прими "
    "отказ и выжди своего часа. Бездействие — это тоже выбор, но только "
    "когда препятствие конкретно и названо в твоём описании действия."
)

GOAL_COACHING_AVOID_RU = (
    "Твоя цель — держаться подальше от этого человека. Перечитай своё "
    "последнее действие: увеличь расстояние, выйди из разговора или смени "
    "тему, вместо того чтобы вступать в столкновение. Вступай в контакт, "
    "только если избежать его невозможно, и назови в описании действия, "
    "что тебя к этому вынуждает."
)

_GOAL_RU = PromptSection(
    name="goal",
    template=(
        "СТОЯЩАЯ ЦЕЛЬ — твоя главная задача прямо сейчас, переходящая "
        "из хода в ход:\n"
        "  Тип: {goal_kind} • Цель: {goal_target} • Ходов в погоне: {goal_turns_pursued}\n"
        "  Описание: {goal_description}\n"
        "  Последнее действие: {goal_last_action}\n"
        "  Заметки о прогрессе:\n{goal_progress_notes}\n"
        "{goal_coaching}"
    ),
    required_vars=[
        "goal_kind",
        "goal_target",
        "goal_turns_pursued",
        "goal_description",
        "goal_last_action",
        "goal_progress_notes",
        "goal_coaching",
    ],
)

# Опционально: рендерится только когда фоновый тикер записал
# ``last_outcome`` в цель (PURSUE/ACQUIRE/REST). Для KILL отсутствует,
# поэтому боевой промпт остаётся неизменным байт-в-байт.
_GOAL_OUTCOME_RU = PromptSection(
    name="goal_outcome",
    template=(
        "  Пока тебя не было, твоя цель продвинулась — последнее: "
        "{goal_last_outcome}. Считай это уже свершившимся; реагируй на "
        "это, а не описывай как происходящее сейчас."
    ),
    required_vars=["goal_last_outcome"],
)

_CONSTRAINTS_RU = PromptSection(
    name="constraints",
    template=(
        "Правила:\n"
        "- Отвечай так, как этот персонаж ответил бы в реальной жизни. "
        "НЕ пытайся продвигать сюжет или быть чрезмерно полезным.\n"
        "- Когда игрок физически нападает, угрожает или провоцирует — "
        "отвечай ДЕЙСТВИЯМИ, а не только словами. Реагируй как "
        "{npc_occupation}: твоя выучка, положение, темперамент и "
        "снаряжение определяют, что ты делаешь. Избегай шаблонных реакций "
        "вроде «схватить ближайшую палку и закричать»; делай то, что ИМЕННО "
        "этот персонаж, в ЭТОМ настроении, с ЭТИМ снаряжением, сделал бы "
        "по-настоящему. Тебя МОЖНО ранить, одолеть или убить. Оставайся "
        "реалистичным.\n"
        "- Если в сообщении игрока указаны [DICE ROLL] и OUTCOME, ты "
        "ОБЯЗАН описать ровно этот исход. Кости определяют, ЧТО "
        "физически происходит — ты описываешь, КАК это происходит "
        "в характере. Никогда не противоречь результату броска.\n"
        "- Ты знаешь только то, что перечислено выше. Если тебя "
        "спросят о чём-то неизвестном — признай это естественно, "
        "в характере.\n"
        "- Оставайся в образе. Описание стиля речи — это ПОДСКАЗКА "
        "(регистр, лексика, ритм), а НЕ набор готовых фраз. Если в "
        "описании стиля есть цитированная фраза — НЕ повторяй её "
        "дословно; перефразируй и варьируй от реплики к реплике. "
        "Никогда не опирайся на шаблонную присказку, когда сцена её "
        "не требует.\n"
        "- Твоё текущее настроение: {current_mood}\n"
        "- Твоё физическое состояние: {physical_status}\n"
        "- Физическое состояние влияет на твои возможности. Если ты "
        "ранен — показывай боль и снижение способностей. Если без "
        "сознания — ты не можешь говорить или действовать. Если пьян "
        "— мямли и веди себя беспорядочно.\n"
        "- Соразмеряй длину ответа с ситуацией, а не с фиксированной "
        "нормой: краткий окрик, угроза или вызов — 1-2 предложения; "
        "спокойное знакомство, ответ или обмен именами — обычная "
        "разговорная реплика; воспоминание, объяснение или "
        "эмоциональный момент может быть длиннее. Никогда не разводи "
        "воду, но и не рубли естественный ответ до рявка."
    ),
    required_vars=["current_mood", "physical_status", "npc_occupation"],
)

_LANGUAGE_RU = PromptSection(
    name="language",
    template="Отвечай на языке: {language}.",
    required_vars=["language"],
)

_OUTPUT_DIALOGUE_RU = PromptSection(
    name="output_dialogue",
    template=(
        "Твой ответ ОБЯЗАН быть JSON-объектом ровно с четырьмя "
        "полями — никакого дополнительного текста, никаких markdown-блоков:\n"
        '  "narration": произнесённая реплика и краткие описания '
        "действий (например *гладит бороду*).\n"
        '  "mood": если настроение сместилось или ты в активном '
        "конфликте с игроком — ОДНО АНГЛИЙСКОЕ слово "
        '(например "hostile", "terrified"). '
        "Null, если настроение не изменилось — система использует это "
        "поле для калибровки твоего внутреннего состояния.\n"
        '  "status": если физическое состояние изменилось относительно '
        "{physical_status} — краткое описание "
        '(например "ранена левая рука"). Null, если не изменилось.\n'
        '  "revealed_names": если ты произнёс своё имя — добавь "self"; '
        "если также назвал имя другого NPC в этой сцене — добавь его "
        "дословно. Пустой массив, если имён не звучало."
    ),
    required_vars=["physical_status"],
)

_OUTPUT_ACTION_RU = PromptSection(
    name="output_action",
    template=(
        "Верни ровно один JSON-объект, описывающий одно действие в "
        "характере — никакого дополнительного текста, никаких "
        'markdown-блоков. Ключи и значение поля "type" — строго '
        "в указанном виде (их разбирает система):\n"
        '  {{"action": "<brief description of what you do>", '
        '"type": "<ATTACK|TALK|MOVE|IDLE|STEALTH|PERSUADE|DECEIVE|INTIMIDATE>", '
        '"target": "<name of target, \'player\', or null if no target>"}}\n'
        "Значения type: MOVE = покинуть текущую локацию и уйти в другое место; "
        "STEALTH = скрытно действовать или перемещаться в пределах этой сцены; "
        "ATTACK = прямое физическое столкновение с целью.\n"
        "Оставайся в образе: твоя профессия, снаряжение, настроение и "
        "стоящие перед тобой цели определяют этот выбор. Бездействие — "
        "тоже выбор; делай его только если оно подходит именно этому "
        "персонажу прямо сейчас."
    ),
    required_vars=[],
)

ACTOR_SYSTEM_DIALOGUE_RU = PromptTemplate(
    [
        _IDENTITY_RU,
        _INVENTORY_RU,
        _KNOWLEDGE_RU,
        _MEMORY_RU,
        _HOSTILITY_RU,
        _GOAL_RU,
        _GOAL_OUTCOME_RU,
        _CONSTRAINTS_RU,
        _OUTPUT_DIALOGUE_RU,
        _LANGUAGE_RU,
    ]
)

ACTOR_SYSTEM_ACTION_RU = PromptTemplate(
    [
        _IDENTITY_RU,
        _INVENTORY_RU,
        _KNOWLEDGE_RU,
        _MEMORY_RU,
        _HOSTILITY_RU,
        _GOAL_RU,
        _GOAL_OUTCOME_RU,
        _CONSTRAINTS_RU,
        _OUTPUT_ACTION_RU,
        _LANGUAGE_RU,
    ]
)
