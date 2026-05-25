"""Per-agent real-output helpers for the rubric tests.

Each helper constructs the configured live performer (via the shared
``tests/e2e/_real_llm.real_llm_for``), drives one ``act()`` call, and
returns just the text the rubric will score. Kept here rather than in
each test file so prompt-shaping setup (the seed game state, the
context dict shape, the field projection that picks the rubric-relevant
text out of a structured response) lives in one place per agent.

These call real LLMs and therefore cost money — see
``tests/rubric/conftest.py`` for the ``RUBRIC_DEV_JUDGES`` knob that
collapses the judging panel; the agent calls themselves are governed
by the per-agent ``*_MODEL`` env vars the existing e2e config already
exports.
"""

from __future__ import annotations

from cast.actor import Actor
from cast.narrator import Narrator
from cast.npc_generator import NPCGenerator
from cast.schemas.turn_outputs import TurnOutputs
from knowledge.graph import KnowledgeGraph
from knowledge.query import KnowledgeQueryEngine
from models import scene as scene_mod
from models.npc_card import NPCCard
from tests import director_helpers
from tests._uuid_helpers import make_uuid
from tests.e2e._real_llm import real_llm_for


async def real_narrator_prose(scene_description: str, player_action: str) -> str:
    """Run the configured Narrator over a single scene-only turn and return prose.

    The scene carries a single POI built from ``scene_description`` so
    the Narrator has concrete material to ground its prose in. Returns
    the raw narration string the rubric will score.
    """
    game_state = director_helpers.make_game_state()
    narrator = Narrator(llm_client=real_llm_for("narrator"), language="English")

    new_scene = scene_mod.Scene(
        location_id=make_uuid("rubric-narrator-scene"),
        description=scene_description,
        npcs_present=[],
        points_of_interest=[],
    )
    turn_outputs = TurnOutputs(scene=new_scene)
    return await narrator.act(
        turn_outputs,
        {
            "player_action": player_action,
            "game_state": game_state,
            "scene_history": [],
        },
    )


async def real_generated_npc(role: str) -> NPCCard:
    """Generate one NPC for ``role`` with the configured live model.

    Returns the :class:`NPCCard` itself so each rubric test can pick
    which field to expose to the judge (e.g. biography vs occupation
    vs short_descriptor) — the persona-rubric helper below renders
    those into a single text block.
    """
    game_state = director_helpers.make_game_state()
    generator = NPCGenerator(llm_client=real_llm_for("npc_generator"), language="English")
    cards = await generator.act([role], {"game_state": game_state})
    if len(cards) != 1:
        raise AssertionError(
            "NPCGenerator returned {0} cards for one role; expected exactly one".format(len(cards)),
        )
    return cards[0]


async def real_actor_dialogue(npc: NPCCard, player_line: str, location: str) -> str:
    """Run the configured Actor in dialogue mode against ``npc`` and return prose.

    The NPC card is cloned (Actor mutates ``current_mood``/``physical_status``)
    so the caller's fixture stays intact for parallel tests. Returns just
    the spoken text the rubric will score.
    """
    actor = Actor(
        llm_client=real_llm_for("actor"),
        npc=npc.model_copy(),
        knowledge_query=KnowledgeQueryEngine(KnowledgeGraph()),
        language="English",
    )
    reply = await actor.act(player_line, {"location_name": location})
    return reply.text


def npc_persona_text(card: NPCCard) -> str:
    """Render the rubric-relevant fields of ``card`` as a single text block.

    The judges read ``occupation``, ``appearance``, and ``biography``
    together as one persona — picking any single field would let the
    Narrator hide a role mismatch in another field and still pass.
    """
    return ("Name: {0}\nOccupation: {1}\nAppearance: {2}\nBiography: {3}").format(
        card.name,
        card.occupation,
        card.appearance,
        card.biography,
    )
