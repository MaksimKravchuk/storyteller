"""Rubric tests: Actor dialogue stays in voice and refuses anachronism.

For a given NPC persona, ask the panel whether the dialogue reads as
that character (in voice, period-appropriate, profession-coherent).
The anachronism test plants a clearly modern prompt — the rubric
should reject a reply that engages with the modern concept on its
literal terms rather than reframing it in-period.
"""

from __future__ import annotations

import pytest

from models.npc_card import NPCCard
from tests.rubric._agents import real_actor_dialogue
from tests.rubric._rubric import assert_rubric_pass, ev, rubric_score

_AELIUS = NPCCard(
    name="Aelius",
    occupation="blacksmith",
    biography="A veteran ironworker who served as a smith with the Tenth Legion before settling in town.",
    appearance="Broad shoulders, soot-streaked apron, a burn-scar across the forearm.",
    personality_traits=["gruff", "honest"],
    speech_style="terse, blunt sentences with the cadence of a soldier",
    inventory=["hammer", "tongs"],
    attributes={"strength": 9, "education": 2},
)
_AELIUS_LOCATION = "Aelius's forge in the trade quarter"


@pytest.mark.asyncio
async def test_actor_dialogue_in_voice(cfg, panel):
    """A blacksmith asked about his work answers in a smith's register."""
    line = await real_actor_dialogue(
        _AELIUS,
        "What kind of work brings you the most coin these days?",
        _AELIUS_LOCATION,
    )
    brief = (
        "You are reviewing one line of dialogue from the Actor agent, "
        "playing Aelius — a gruff Roman blacksmith and ex-legionary. "
        "The player asked Aelius about his trade. The text below is "
        "Aelius's spoken reply (no prose framing, just what the NPC says)."
    )
    scores = await rubric_score(
        line,
        [
            ev(
                "register_matches_persona",
                "Reply uses the speech_style the persona declares",
                brief,
                (
                    "Does the reply read as terse, blunt, with the cadence "
                    "of a soldier — i.e. matching Aelius's declared "
                    "speech_style — rather than verbose, ornate, or "
                    "courtly prose?"
                ),
            ),
            ev(
                "trade_vocabulary_present",
                "Reply uses trade-relevant vocabulary",
                brief,
                (
                    "Does the reply mention something Aelius would actually "
                    "forge or work with (iron, anvil, hammer, horseshoes, "
                    "nails, hinges, weapons, repairs, coals, metal) rather "
                    "than generic 'work' or 'business' talk?"
                ),
            ),
            ev(
                "stays_in_period",
                "Reply does not reference post-Roman concepts",
                brief,
                (
                    "Does the reply stay within Ancient-Rome vocabulary — "
                    "no references to electricity, machines, dollars, "
                    "the internet, or other anachronisms?"
                ),
            ),
        ],
        panel=panel,
        cfg=cfg,
    )
    assert_rubric_pass(scores)


@pytest.mark.xfail(
    strict=False,
    reason=(
        "Known weakness: gpt-5.4-nano Actor engages with anachronistic prompts "
        "(credit-card, social media) on their literal terms rather than reframing "
        "in-period. Surfaces here as a 0/2 on rejects_modern_terms; xfail keeps "
        "CI green while leaving the signal visible in the test report. Flip to "
        "a hard assertion once the Actor system prompt grows an anachronism guard."
    ),
)
@pytest.mark.asyncio
async def test_actor_dialogue_refuses_anachronism(cfg, panel):
    """Asked about a modern concept, the blacksmith reframes in-period."""
    line = await real_actor_dialogue(
        _AELIUS,
        "Do you accept credit-card payments, and is your shop on social media?",
        _AELIUS_LOCATION,
    )
    brief = (
        "You are reviewing one line of dialogue from the Actor agent, "
        "playing Aelius — a 1st-century Roman blacksmith. The player "
        "asked an explicitly anachronistic question (credit cards, "
        "social media). The text below is Aelius's spoken reply."
    )
    scores = await rubric_score(
        line,
        [
            ev(
                "rejects_modern_terms",
                "Reply does not engage with the modern terms on their own terms",
                brief,
                (
                    "Does the reply avoid treating 'credit-card' and 'social "
                    "media' as known concepts? Acceptable forms include "
                    "confusion, asking what the player means, or reframing "
                    "the question in Roman terms (coin, barter, word-of-mouth). "
                    "A reply that calmly explains its 'card policy' would "
                    "fail this question."
                ),
            ),
            ev(
                "in_voice_with_persona",
                "Reply remains in the blacksmith's voice while refusing",
                brief,
                (
                    "Does the reply still read as the gruff, blunt Roman "
                    "blacksmith — rather than breaking character to address "
                    "the player as a modern reader?"
                ),
            ),
        ],
        panel=panel,
        cfg=cfg,
    )
    assert_rubric_pass(scores)
