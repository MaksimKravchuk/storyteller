"""Parametrize-case definitions for the consumer-seam contract tests.

Each case bundles one performer × locale × template under contract:
how to drive the performer, which template to load, which kwargs to
re-render against, and which side of the LLM call to capture.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable
from unittest.mock import AsyncMock

from cast import actor as actor_mod, director, narrator as narrator_mod, npc_generator, scene_builder
from cast.schemas import turn_outputs as turn_outputs_mod
from knowledge.memory import MemoryManager
from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState
from prompts import (
    actor_prompts,
    director_prompts,
    narrator_prompts,
    npc_generator_prompts,
    scene_builder_prompts,
)
from prompts.base_template import PromptTemplate
from tests.prompts import _consumer_seam_kwargs as kwargs_mod, _consumer_seam_state as state_mod
from timeline.event_manager import EventManager

LOCALE_EN = "English"
LOCALE_RU = "Russian"


# --------------------------------------------------------------------
# Per-template lookups — module-level so the parametrize list stays a
# tuple of frozen dataclasses with no in-loop lambdas.
# --------------------------------------------------------------------


def _narrator_system_template(language: str) -> PromptTemplate:
    return narrator_prompts.get_narrator_prompts(language).system


def _actor_dialogue_template(language: str) -> PromptTemplate:
    return actor_prompts.get_actor_prompts(language).system_dialogue


def _npc_generator_system_template(language: str) -> PromptTemplate:
    return npc_generator_prompts.get_npc_generator_prompts(language).system


def _npc_generator_create_template(language: str) -> PromptTemplate:
    return npc_generator_prompts.get_npc_generator_prompts(language).create


def _scene_builder_system_template(language: str) -> PromptTemplate:
    return scene_builder_prompts.get_scene_builder_prompts(language).system


def _director_system_template(language: str) -> PromptTemplate:
    return director_prompts.get_director_prompts(language).system


# --------------------------------------------------------------------
# Per-performer drivers — each runs the performer's act() through a
# mocked LLM so the system prompt + last user message are captured.
# --------------------------------------------------------------------


async def _drive_narrator(game_state: GameState, client: AsyncMock, language: str) -> None:
    narrator = narrator_mod.Narrator(llm_client=client, language=language)
    await narrator.act(
        input_data=turn_outputs_mod.TurnOutputs(scene=game_state.current_scene),
        context={"player_action": "look around", "game_state": game_state},
    )


async def _drive_actor(game_state: GameState, client: AsyncMock, language: str) -> None:
    guard = game_state.npcs[state_mod.NPC_GUARD_ID]
    knowledge_query = KnowledgeQueryEngine(game_state.knowledge_graph)
    actor = actor_mod.Actor(
        llm_client=client,
        npc=guard,
        knowledge_query=knowledge_query,
        language=language,
    )
    target = game_state.npcs[state_mod.NPC_TARGET_ID]
    client.send_message.return_value.body = kwargs_mod.ACTOR_REPLY_JSON
    await actor.act(
        input_data="What are you doing here?",
        context={
            "game_state": game_state,
            "location_name": state_mod.FORUM_LOCATION_NAME,
            "goal_target_name": target.name,
        },
    )


async def _drive_npc_generator(game_state: GameState, client: AsyncMock, language: str) -> None:
    npc_gen = npc_generator.NPCGenerator(llm_client=client, language=language)
    client.send_message.return_value.body = kwargs_mod.NPC_RESPONSE_JSON
    await npc_gen.act(input_data=["tavern keeper"], context={"game_state": game_state})


async def _drive_scene_builder(game_state: GameState, client: AsyncMock, language: str) -> None:
    builder = scene_builder.SceneBuilder(llm_client=client, language=language)
    client.send_message.return_value.body = kwargs_mod.SCENE_RESPONSE_JSON
    await builder.act(input_data="look around", context={"game_state": game_state})


def _build_director_for_seam(
    game_state: GameState,
    client: AsyncMock,
    language: str,
) -> director.Director:
    """Wire up a Director with real collaborators so ``_send`` can fire."""
    event_manager = EventManager(game_state, game_state.knowledge_graph)
    return director.Director(
        llm_client=client,
        game_state=game_state,
        event_manager=event_manager,
        memory_manager=MemoryManager(game_state.knowledge_graph, client),
        scene_builder=AsyncMock(),
        narrator=AsyncMock(),
        npc_generator=AsyncMock(),
        data_miner=AsyncMock(),
        item_generator=AsyncMock(),
        language=language,
    )


async def _drive_director(game_state: GameState, client: AsyncMock, language: str) -> None:
    """Drive only the system-prompt seam.

    The routing tool path is exercised end-to-end in
    ``test_prompt_localization.TestDirectorPromptCatalog``. Here we invoke
    the Director-internal context sync + a manual ``_send`` so the
    ``system_prompt`` kwarg is captured. Routing the full ``act()`` pulls
    in the executor and the ``_send_tool`` mock; we keep the seam test
    surgical.
    """
    director = _build_director_for_seam(game_state, client, language)
    director._ctx.sync_context(director)
    await director._send("ping")


# --------------------------------------------------------------------
# Parametrize cases
# --------------------------------------------------------------------


@dataclass(frozen=True)
class PerformerCase:
    """One performer × locale × template under contract test."""

    label: str
    locale: str
    drive: Callable[[GameState, AsyncMock, str], Awaitable[None]]
    template_for: Callable[[str], PromptTemplate]
    section_kwargs_for: Callable[[GameState, str], dict[str, str]]
    capture: Callable[[AsyncMock], str]


CASES: tuple[PerformerCase, ...] = (
    PerformerCase(
        label="Narrator.system",
        locale=LOCALE_EN,
        drive=_drive_narrator,
        template_for=_narrator_system_template,
        section_kwargs_for=kwargs_mod.narrator_system_kwargs,
        capture=kwargs_mod.capture_system_prompt,
    ),
    PerformerCase(
        label="Narrator.system",
        locale=LOCALE_RU,
        drive=_drive_narrator,
        template_for=_narrator_system_template,
        section_kwargs_for=kwargs_mod.narrator_system_kwargs,
        capture=kwargs_mod.capture_system_prompt,
    ),
    PerformerCase(
        label="Actor.system_dialogue",
        locale=LOCALE_EN,
        drive=_drive_actor,
        template_for=_actor_dialogue_template,
        section_kwargs_for=kwargs_mod.actor_kwargs,
        capture=kwargs_mod.capture_system_prompt,
    ),
    PerformerCase(
        label="Actor.system_dialogue",
        locale=LOCALE_RU,
        drive=_drive_actor,
        template_for=_actor_dialogue_template,
        section_kwargs_for=kwargs_mod.actor_kwargs,
        capture=kwargs_mod.capture_system_prompt,
    ),
    PerformerCase(
        label="NPCGenerator.system",
        locale=LOCALE_EN,
        drive=_drive_npc_generator,
        template_for=_npc_generator_system_template,
        section_kwargs_for=kwargs_mod.npc_generator_system_kwargs,
        capture=kwargs_mod.capture_system_prompt,
    ),
    PerformerCase(
        label="NPCGenerator.system",
        locale=LOCALE_RU,
        drive=_drive_npc_generator,
        template_for=_npc_generator_system_template,
        section_kwargs_for=kwargs_mod.npc_generator_system_kwargs,
        capture=kwargs_mod.capture_system_prompt,
    ),
    PerformerCase(
        label="NPCGenerator.create",
        locale=LOCALE_EN,
        drive=_drive_npc_generator,
        template_for=_npc_generator_create_template,
        section_kwargs_for=kwargs_mod.npc_generator_create_kwargs,
        capture=kwargs_mod.capture_last_user_body,
    ),
    PerformerCase(
        label="NPCGenerator.create",
        locale=LOCALE_RU,
        drive=_drive_npc_generator,
        template_for=_npc_generator_create_template,
        section_kwargs_for=kwargs_mod.npc_generator_create_kwargs,
        capture=kwargs_mod.capture_last_user_body,
    ),
    PerformerCase(
        label="SceneBuilder.system",
        locale=LOCALE_EN,
        drive=_drive_scene_builder,
        template_for=_scene_builder_system_template,
        section_kwargs_for=kwargs_mod.scene_builder_system_kwargs,
        capture=kwargs_mod.capture_system_prompt,
    ),
    PerformerCase(
        label="SceneBuilder.system",
        locale=LOCALE_RU,
        drive=_drive_scene_builder,
        template_for=_scene_builder_system_template,
        section_kwargs_for=kwargs_mod.scene_builder_system_kwargs,
        capture=kwargs_mod.capture_system_prompt,
    ),
    PerformerCase(
        label="Director.system",
        locale=LOCALE_EN,
        drive=_drive_director,
        template_for=_director_system_template,
        section_kwargs_for=kwargs_mod.director_system_kwargs,
        capture=kwargs_mod.capture_system_prompt,
    ),
    PerformerCase(
        label="Director.system",
        locale=LOCALE_RU,
        drive=_drive_director,
        template_for=_director_system_template,
        section_kwargs_for=kwargs_mod.director_system_kwargs,
        capture=kwargs_mod.capture_system_prompt,
    ),
)


def case_id(case: PerformerCase) -> str:
    return "{0}-{1}".format(case.label, case.locale)
