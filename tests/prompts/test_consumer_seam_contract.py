"""Consumer-seam contract tests for prompt templates.

This module guards a documented past-regression class:
``PromptTemplate.render`` silently *skips* any ``PromptSection`` whose
``required_vars`` are not all present in the kwargs (see
``prompts/base_template.py``). The risk is a producer agent populating
a model field (e.g. ``NPCCard.known_names_for_player``) whose consumer
agent never reads it onto its template kwargs — the section drops
silently, the prompt looks plausible to an LLM, and the regression
ships.

For every critical performer (Narrator, Actor, NPCGenerator, Director,
SceneBuilder), this module:

1. Builds a *maximal* game-state fixture so every PromptSection's
   ``required_vars`` (including intentionally optional ones — Actor's
   memory/hostility/goal, Narrator's world_mood, etc.) has its
   preconditions satisfied by real data on the game state. Fixture
   helpers live in ``_consumer_seam_state.py`` / ``_consumer_seam_kwargs.py``
   / ``_consumer_seam_cases.py`` (split for the WPS import-count budget).
2. Drives the performer's ``act()`` through a mocked LLM.
3. Captures the system prompt actually sent to the LLM via
   ``llm_client.send_message.call_args.kwargs["system_prompt"]`` —
   the same seam ``cast/base_performer_class.py`` writes to at
   ``_call_llm`` — and the last user message body.
4. Re-renders each ``PromptSection`` individually against the same
   context and asserts every rendered section appears in the captured
   prompt. A consumer that forgets to populate a section's required
   vars makes that section drop, which makes the substring assert
   fail with a clear "section X missing from rendered prompt" message.

A separate ``TestContrivedBugIsCaught`` class proves the assertion is
load-bearing: it uses ``monkeypatch`` to drop a known-required Actor
``physical_status`` kwarg and asserts that the contract assertion
above fires with a locatable AssertionError.

## Adding a new performer

When introducing a new ``BasePerformer`` subclass:

1. Add a section-kwargs builder to ``_consumer_seam_kwargs.py`` mirroring
   the new performer's ``set_context`` calls (including conditional
   / optional sections — read the consumer's ``act()`` and reverse the
   conditions).
2. Add a driver + a ``PerformerCase`` to ``_consumer_seam_cases.py``
   covering both ``"English"`` and ``"Russian"`` locales.
3. Update ``build_maximal_game_state()`` in ``_consumer_seam_state.py``
   if your performer needs new game-state preconditions to satisfy a
   new section's required vars.
"""

from __future__ import annotations

from typing import Any

import allure
import pytest

from cast import actor as actor_mod
from knowledge.query import KnowledgeQueryEngine
from prompts.actor_prompts import ACTOR_SYSTEM_DIALOGUE
from prompts.base_template import PromptTemplate
from tests.prompts import (
    _consumer_seam_cases as cases_mod,
    _consumer_seam_kwargs as kwargs_mod,
    _consumer_seam_state as state_mod,
)

# --------------------------------------------------------------------
# Section presence assertion — re-renders each section against the
# same kwargs the consumer should have set, then asserts the rendered
# text is a substring of the prompt actually sent to the LLM.
# --------------------------------------------------------------------


def _render_section(section: Any, section_kwargs: dict[str, str]) -> str:
    """Render a section against ``section_kwargs`` (or its raw template if no vars)."""
    if not section.required_vars:
        return section.template
    selected = {var_name: section_kwargs[var_name] for var_name in section.required_vars}
    return section.render(**selected)


def _section_signature(rendered_section: str) -> str:
    """Return a short stable substring of a rendered section.

    Picks the first non-empty line so the signature reflects content,
    not a leading blank, and trims to keep the assertion message tight.
    """
    for line in rendered_section.split("\n"):
        stripped = line.strip()
        if stripped:
            return stripped[:60]
    return rendered_section[:60]


def _assert_every_section_present(
    template: PromptTemplate,
    captured_prompt: str,
    section_kwargs: dict[str, str],
) -> None:
    """Assert each section of ``template`` rendered into ``captured_prompt``.

    A section that ``PromptTemplate.render`` silently dropped because the
    consumer forgot a required var will produce an empty rendered chunk
    and not appear in the captured prompt — this assertion makes that
    failure mode loud and locatable.
    """
    for section in template._sections:
        rendered = _render_section(section, section_kwargs)
        signature = _section_signature(rendered)
        assert signature in captured_prompt, (
            "PromptSection '{0}' missing from rendered prompt — "
            "consumer-seam regression: a required var was not "
            "populated by the consumer agent."
        ).format(section.name)


@allure.epic("Narrative Delivery")
@allure.feature("Prompt consumer-seam contract")
class TestConsumerSeamContract:
    """Per-performer contract: every PromptSection's required vars must be
    populated by the consumer agent on every ``act()`` call.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", cases_mod.CASES, ids=cases_mod.case_id)
    @allure.story("Section-presence contract")
    @allure.title("Every PromptSection renders into the prompt actually sent to the LLM")
    async def test_every_section_renders_into_captured_prompt(
        self,
        case: cases_mod.PerformerCase,
    ) -> None:
        game_state = state_mod.build_maximal_game_state()
        client = kwargs_mod.make_mock_llm()

        # Snapshot the expected section kwargs BEFORE driving: a consumer may
        # legitimately consume one-shot state during act() (e.g. the Actor
        # clears a goal's off-scene outcome after rendering it), so kwargs
        # recomputed post-drive would no longer match the captured prompt.
        template = case.template_for(case.locale)
        section_kwargs = case.section_kwargs_for(game_state, case.locale)

        await case.drive(game_state, client, case.locale)

        captured = case.capture(client)
        _assert_every_section_present(template, captured, section_kwargs)


# --------------------------------------------------------------------
# Contrived-bug demonstration: prove the contract catches a consumer
# that forgets a required var.
# --------------------------------------------------------------------


_DROPPED_KWARG = "physical_status"


def _set_context_dropping_physical_status(performer: Any, **kwargs: str) -> None:
    """Patched ``Actor.set_context`` that silently drops ``physical_status``.

    Simulates a consumer-side regression where the consumer forgets to
    pass the required var — the same shape as the documented past
    regression class. Bypasses the parent ``set_context`` and writes
    directly to ``_system_prompt_vars`` so this stays a module-level
    function (no nested closure) and remains a valid descriptor when
    assigned onto ``Actor`` via ``monkeypatch.setattr``.
    """
    kwargs.pop(_DROPPED_KWARG, None)
    performer._system_prompt_vars.update(kwargs)


@allure.epic("Narrative Delivery")
@allure.feature("Prompt consumer-seam contract")
class TestContrivedBugIsCaught:
    """Proves the section-presence assertion is load-bearing.

    Drops a known-required var (``physical_status``) from the Actor's
    context via ``monkeypatch`` and asserts the contract assertion
    fires with a locatable AssertionError. Both ``constraints`` and
    ``output_dialogue`` list ``physical_status`` in their
    ``required_vars``, so the silent-skip behaviour drops them.
    """

    @pytest.mark.asyncio
    @allure.story("Contrived bug — contract assertion fires")
    @allure.title("Dropping the Actor's physical_status kwarg makes the contract assertion fail")
    async def test_contract_assertion_fires_on_dropped_section(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        game_state = state_mod.build_maximal_game_state()
        client = kwargs_mod.make_mock_llm()
        guard = game_state.npcs[state_mod.NPC_GUARD_ID]
        knowledge_query = KnowledgeQueryEngine(game_state.knowledge_graph)

        monkeypatch.setattr(
            actor_mod.Actor,
            "set_context",
            _set_context_dropping_physical_status,
        )

        actor = actor_mod.Actor(
            llm_client=client,
            npc=guard,
            knowledge_query=knowledge_query,
            language=cases_mod.LOCALE_EN,
        )
        client.send_message.return_value.body = kwargs_mod.ACTOR_REPLY_JSON
        # Snapshot expected kwargs before act() — act() consumes one-shot
        # state (clears the goal's off-scene outcome) that post-act kwargs
        # would no longer carry.
        section_kwargs = kwargs_mod.actor_kwargs(game_state, cases_mod.LOCALE_EN)
        await actor.act(
            input_data="What are you doing here?",
            context={
                "location_name": state_mod.FORUM_LOCATION_NAME,
                "goal_target_name": "Marcus Cinna",
            },
        )

        captured = kwargs_mod.capture_system_prompt(client)
        # Both ``constraints`` and ``output_dialogue`` list physical_status
        # in their required_vars; the assertion fails on the first one it
        # checks, so we match either name.
        with pytest.raises(AssertionError, match=r"(constraints|output_dialogue)"):
            _assert_every_section_present(ACTOR_SYSTEM_DIALOGUE, captured, section_kwargs)


# Note: the Director's plain-string ``action_routing`` template has no
# PromptSection-driven skips to guard against. The locale-parity check
# in ``tests/test_prompt_localization.py::TestDirectorPromptCatalog
# ::test_action_router_sends_russian_template_to_llm`` already exercises
# the ActionRouter seam end-to-end and is the right gate.
