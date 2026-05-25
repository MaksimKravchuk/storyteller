"""Real-model Narrator smoke tests.

Drive the Narrator with the configured live model and assert that
distinctive input values (a unique NPC name, a unique POI name) survive
into the rendered prose. These input-tied assertions catch the regression
class the mocked unit tests cannot: prompt-template variables that fail
to render, dialogue entries dropped from the prompt body, or scene
context that never reaches the model.
"""

from __future__ import annotations

import allure
import pytest

from cast.narrator import Narrator
from cast.schemas.turn_outputs import DialogueEntry, TurnOutputs
from models import npc_card as npc_mod, scene as scene_mod
from tests import director_helpers
from tests._uuid_helpers import make_uuid
from tests.e2e._real_llm import real_llm_for

# Distinctive values chosen so a sloppy match (e.g. on a generic word) is
# unlikely to score a false positive. Both names are uncommon enough in
# the Roman setting that the LLM would not introduce them unprompted.
_NPC_NAME = "Quintus"
_NPC_QUOTE = "The grain shipment never reached the warehouse, dominus."
_POI_NAME = "obsidian fountain"
_FORUM_ID = make_uuid("narrator-real-forum")
_QUINTUS_ID = make_uuid("narrator-real-quintus")


@allure.epic("AI Agent Orchestration")
@allure.feature("Narrator real-model rendering")
class TestNarratorRealModel:
    @allure.story("Dialogue survives into prose")
    @allure.title("A real Narrator model renders a dialogue speaker's name into the narration")
    @pytest.mark.asyncio
    async def test_real_model_renders_dialogue_speaker_name(self):
        game_state = director_helpers.make_game_state()
        narrator = Narrator(llm_client=real_llm_for("narrator"), language="English")

        turn_outputs = TurnOutputs(
            dialogue=[
                DialogueEntry(
                    npc_uuid=_QUINTUS_ID,
                    npc_name=_NPC_NAME,
                    response=_NPC_QUOTE,
                ),
            ],
        )
        # Register Quintus both as an NPCCard in game_state.npcs (so the
        # alias resolver can look him up) and on the player's known list
        # (so the gate emits his proper name rather than a "the steward"
        # placeholder). Production wires both up through
        # ``cast.director_execution.PlanExecutor`` during the turn flow.
        quintus = npc_mod.NPCCard(name=_NPC_NAME, occupation="steward")
        quintus.uuid = _QUINTUS_ID
        game_state.npcs[_QUINTUS_ID] = quintus
        game_state.player.known_npcs.add(_QUINTUS_ID)

        prose = await narrator.act(
            turn_outputs,
            {
                "player_action": "Ask the steward what happened to the grain shipment.",
                "game_state": game_state,
                "scene_history": [],
            },
        )

        assert isinstance(prose, str)
        assert prose.strip(), "Narrator returned empty prose"
        # Input-tied: the speaker's distinctive name must appear in prose.
        # Failure mode this catches: dialogue list dropped from the
        # prompt body, or npc_name field not piped through alias rendering.
        assert _NPC_NAME.lower() in prose.lower(), (
            "Narrator output did not surface dialogue speaker name {0!r}.\nProse was:\n{1}".format(_NPC_NAME, prose)
        )

    @allure.story("Scene POI surfaces in narration")
    @allure.title("A real Narrator model surfaces a scene's distinctive point of interest")
    @pytest.mark.asyncio
    async def test_real_model_surfaces_scene_point_of_interest(self):
        game_state = director_helpers.make_game_state()
        narrator = Narrator(llm_client=real_llm_for("narrator"), language="English")

        new_scene = scene_mod.Scene(
            location_id=_FORUM_ID,
            description=(
                "A torch-lit Roman atrium dominated by an unusual {0} carved from a single block. "
                "The air smells of cypress smoke."
            ).format(_POI_NAME),
            npcs_present=[],
            points_of_interest=[scene_mod.PointOfInterest(names=[_POI_NAME])],
        )
        turn_outputs = TurnOutputs(scene=new_scene)

        prose = await narrator.act(
            turn_outputs,
            {
                "player_action": "Step into the atrium and look around.",
                "game_state": game_state,
                "scene_history": [],
            },
        )

        assert isinstance(prose, str)
        assert prose.strip(), "Narrator returned empty prose"
        # Input-tied: the distinctive POI substring "obsidian" or "fountain"
        # must appear. Failure mode this catches: scene context not
        # rendered into the narration prompt at all.
        lower = prose.lower()
        assert "obsidian" in lower or "fountain" in lower, (
            "Narrator output did not surface scene POI {0!r}.\nProse was:\n{1}".format(_POI_NAME, prose)
        )
