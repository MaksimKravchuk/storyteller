"""Rubric tests: NPCGenerator persona fidelity for distinctive roles.

For each requested role, ask the panel whether the resulting NPCCard's
combined occupation+appearance+biography reads as a believable instance
of that role. Bundled as one multi-element rubric per persona — see the
threshold rationale in :mod:`tests.rubric.test_narrator_prose`.
"""

from __future__ import annotations

import pytest

from tests.rubric._agents import npc_persona_text, real_generated_npc
from tests.rubric._rubric import assert_rubric_pass, ev, rubric_score


def _persona_brief(role: str) -> str:
    """Build the judge-facing brief for an NPC persona rubric."""
    return (
        "You are reviewing one NPC the NPCGenerator agent produced when "
        "asked for the role '{0}' in an Ancient-Rome setting. "
        "The text below renders the card's name, occupation, appearance, "
        "and biography fields."
    ).format(role)


def _persona_rubric(role: str, brief: str) -> list:
    """Build the standard 3-element persona rubric (6 base points)."""
    return [
        ev(
            "role_matches",
            "Persona reads as the requested role",
            brief,
            (
                "Does the NPC card (occupation, appearance, biography) "
                "describe a person whose profession is clearly recognisable "
                "as '{0}' or a close synonym, rather than an unrelated "
                "occupation?"
            ).format(role),
        ),
        ev(
            "appearance_supports_role",
            "Appearance details support the role",
            brief,
            (
                "Does the appearance field contain physical or sartorial "
                "details consistent with someone who works as '{0}' "
                "(tools of the trade, work-induced wear, clothing of the "
                "right station)?"
            ).format(role),
        ),
        ev(
            "biography_supports_role",
            "Biography places the NPC in the role's social context",
            brief,
            (
                "Does the biography place this person in a setting where "
                "they would plausibly be a '{0}' (training, prior service, "
                "social station, life events that make the role coherent)?"
            ).format(role),
        ),
    ]


@pytest.mark.asyncio
async def test_npc_generator_blind_beggar_persona(cfg, panel):
    """A 'blind beggar' card reads as a destitute, infirm street figure."""
    card = await real_generated_npc("blind beggar")
    scores = await rubric_score(
        npc_persona_text(card),
        _persona_rubric("blind beggar", _persona_brief("blind beggar")),
        panel=panel,
        cfg=cfg,
    )
    assert_rubric_pass(scores)


@pytest.mark.asyncio
async def test_npc_generator_roman_senator_persona(cfg, panel):
    """A 'Roman senator' card reads as a patrician statesman."""
    card = await real_generated_npc("Roman senator")
    scores = await rubric_score(
        npc_persona_text(card),
        _persona_rubric("Roman senator", _persona_brief("Roman senator")),
        panel=panel,
        cfg=cfg,
    )
    assert_rubric_pass(scores)
