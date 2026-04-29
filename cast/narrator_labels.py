"""Locale-aware connector strings used by the Narrator agent.

The Narrator assembles a list of "raw material" bullets (``Scene:``,
``Atmosphere:``, ``People visible:``, ``Meanwhile, <name>:`` and so
on) that are fed as the user message to the LLM. Historically these
labels were English-only, so even when the Narrator system prompt
instructed the model to "write all your output in Russian" the raw
material itself was still English — which degrades the quality of the
generated narration.

:class:`NarratorLabels` bundles every such connector string for one
locale. :func:`get_narrator_labels` returns the bundle for the
player's chosen language, with a graceful fallback to English for
unsupported locales.
"""

from __future__ import annotations

from dataclasses import dataclass

from prompts.locales import Locale, make_locale_lookup


@dataclass(frozen=True)
class NarratorLabels:
    """Connector words rendered into the Narrator's raw-material block.

    Every field is a *format string* — some embed a single ``{0}``
    placeholder so the call site can inject dynamic content (NPC name,
    object description, etc.) while keeping the label itself localised.
    """

    # Scene block
    scene: str
    atmosphere: str
    people_visible: str
    notable_things: str
    prior_damage: str
    # Per-turn bullets
    says: str  # "{name} says: {text}"
    new_person: str  # "New person appears: {desc}"
    item_examined: str  # "Item examined: {desc}"
    object_interaction: str  # "Object interaction: {desc}"
    someone_departs: str  # "Someone departs: {line}"
    meanwhile: str  # "Meanwhile, {name}: {action}"
    # Scene history preamble
    scene_history_heading: str
    scene_history_player_line: str  # "- Player: {action} → {summary}"
    # Wait bullets
    waits_and_observes: str  # stub fallback
    cannot_act: str  # "The player cannot act — they are {reason}."
    waits_for_hours: str  # "The player waits for roughly {hours:.1f} hours."
    ongoing_thread: str  # "Ongoing thread: {desc}"
    on_shift_nearby: str  # "On shift nearby: {label}"
    stirring_background: str  # "Stirring in the background: {line}"
    # Wait context bullets (rendered into narrate.wait_context template)
    wait_bullet_thread: str  # "- thread: {desc}"
    wait_bullet_on_shift: str  # "- on shift: {label}"
    wait_bullet_stirring: str  # "- stirring: {line}"
    # No-material placeholder
    no_scene_data: str


_ENGLISH = NarratorLabels(
    scene="Scene: {0}",
    atmosphere="Atmosphere: {0}",
    people_visible="People visible: {0}",
    notable_things="Notable things: {0}",
    prior_damage="Prior damage:\n{0}",
    says="{0} says: {1}",
    new_person="New person appears: {0}",
    item_examined="Item examined: {0}",
    object_interaction="Object interaction: {0}",
    someone_departs="Someone departs: {0}",
    meanwhile="Meanwhile, {0}: {1}",
    scene_history_heading="What happened earlier in this scene:\n{0}",
    scene_history_player_line="- Player: {0} → {1}",
    waits_and_observes="The player waits and observes the surroundings.",
    cannot_act="The player cannot act — they are {0}.",
    waits_for_hours="The player waits for roughly {0:.1f} hours.",
    ongoing_thread="Ongoing thread: {0}",
    on_shift_nearby="On shift nearby: {0}",
    stirring_background="Stirring in the background: {0}",
    wait_bullet_thread="- thread: {0}",
    wait_bullet_on_shift="- on shift: {0}",
    wait_bullet_stirring="- stirring: {0}",
    no_scene_data="No specific scene data.",
)


_RUSSIAN = NarratorLabels(
    scene="Сцена: {0}",
    atmosphere="Атмосфера: {0}",
    people_visible="Видимые люди: {0}",
    notable_things="Заметные предметы: {0}",
    prior_damage="Прежние повреждения:\n{0}",
    says="{0} говорит: {1}",
    new_person="Появляется новый человек: {0}",
    item_examined="Осмотренный предмет: {0}",
    object_interaction="Взаимодействие с объектом: {0}",
    someone_departs="Кто-то уходит: {0}",
    meanwhile="Тем временем {0}: {1}",
    scene_history_heading="Что произошло раньше в этой сцене:\n{0}",
    scene_history_player_line="- Игрок: {0} → {1}",
    waits_and_observes="Игрок ждёт и наблюдает за происходящим.",
    cannot_act="Игрок не может действовать — он {0}.",
    waits_for_hours="Игрок ждёт примерно {0:.1f} ч.",
    ongoing_thread="Текущая линия: {0}",
    on_shift_nearby="На дежурстве рядом: {0}",
    stirring_background="Движение на заднем плане: {0}",
    wait_bullet_thread="- линия: {0}",
    wait_bullet_on_shift="- на дежурстве: {0}",
    wait_bullet_stirring="- движение: {0}",
    no_scene_data="Особых данных по сцене нет.",
)


get_narrator_labels = make_locale_lookup(
    {
        Locale.ENGLISH: _ENGLISH,
        Locale.RUSSIAN: _RUSSIAN,
    }
)
