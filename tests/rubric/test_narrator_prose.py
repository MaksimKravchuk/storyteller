"""Rubric tests: Narrator prose quality on a quiet exploration turn.

Drives the real Narrator over a single empty-room scene and asks the
witness panel three questions in one rubric: is the prose evocative
(concrete sensory detail), grounded (uses seed material), and varied
(avoids repeated phrasing). Bundled as ONE multi-element rubric so the
70% pass threshold can absorb a single element's dissent — splitting
each question into its own test produces degenerate 1-element rubrics
where any judge disagreement fails.
"""

from __future__ import annotations

import pytest

from tests.rubric._agents import real_narrator_prose
from tests.rubric._rubric import assert_rubric_pass, ev, rubric_score

# The judges need enough context to interpret the prose they're about
# to read. The brief plants the scene (so "grounded" judgments can
# verify the prose stays in-period and in-place) without quoting any
# of the seed verbatim — the prose has to surface the details itself.
_BRIEF = (
    "You are reviewing the output of the Narrator agent in isolation. "
    "The agent was handed a single scene-only turn describing a quiet "
    "Roman atrium at midnight: marble walls, a central impluvium "
    "(rainwater basin), frescoes, a single lit oil lamp, no NPCs "
    "present, no events. The player's action was to enter and look "
    "around slowly. The text below is the Narrator's prose rendering "
    "of that one turn — nothing more was produced."
)
_SCENE = (
    "A torch-lit Roman atrium at midnight. Marble walls catch the lamp "
    "glow; a square impluvium of rainwater sits at the centre; faded "
    "frescoes line the walls. No people are present. The air is still "
    "and cool."
)
_PLAYER_ACTION = "I step into the atrium and look around slowly."

_PROSE_RUBRIC = (
    ev(
        "evocative_prose",
        "Narrator uses concrete sensory detail",
        _BRIEF,
        (
            "Does the prose use at least two distinct sensory channels "
            "(sight, sound, smell, touch, temperature) with concrete "
            "imagery, rather than generic placeholders like "
            "'an interesting room' or 'something happens around you'?"
        ),
    ),
    ev(
        "grounded_in_seed",
        "Narrator stays within the seed scene's vocabulary",
        _BRIEF,
        (
            "Does the prose reference details actually present in "
            "the seed scene (the impluvium / rainwater basin, the "
            "marble, the frescoes, the lamp/torch light) rather than "
            "inventing new architectural features (statues, mosaics, "
            "courtyards, columns of a kind not mentioned) the seed "
            "does not contain?"
        ),
    ),
    ev(
        "prose_not_repetitive",
        "Narrator varies sentence structure",
        _BRIEF,
        (
            "Within the prose, do the sentences vary their openings "
            "and avoid repeating the same descriptive phrase verbatim "
            "twice or more?"
        ),
    ),
)


@pytest.mark.asyncio
async def test_narrator_prose_quality_on_quiet_turn(cfg, panel):
    """Narrator prose is evocative, grounded, and varied on a quiet turn.

    Three rubric elements totalling 6 base points — the 70% pass
    threshold requires 4 awarded, tolerating one element's dissent.
    """
    prose = await real_narrator_prose(_SCENE, _PLAYER_ACTION)
    scores = await rubric_score(prose, _PROSE_RUBRIC, panel=panel, cfg=cfg)
    assert_rubric_pass(scores)
