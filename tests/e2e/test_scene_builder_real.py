"""Real-model SceneBuilder smoke tests.

The SceneBuilder fabricates a fresh :class:`models.scene.Scene` from a
player action and the current ``GameState``. We pin the assertions to
distinctive nouns we put into the prompt (a landmark in the action, a
seeded social premise) so a prompt-template regression that drops the
context cannot pass silently.
"""

from __future__ import annotations

import allure
import pytest

from cast.scene_builder import _GENERIC_SOCIAL_ROLES, SceneBuilder
from models.scene import Scene, SceneNPC
from tests import director_helpers
from tests.e2e._real_llm import real_llm_for

_LANDMARK_KEYWORDS = ("lighthouse", "pharos")
# These two strings are crafted to match production's marker tuples in
# ``cast/scene_builder.py``: ``_OPENING_ACTION_MARKERS`` ("look around")
# and ``_SOCIAL_PREMISE_MARKERS`` ("investigation", "witnesses",
# "rumor"). Without the markers the deterministic Aurelia fallback
# never fires and the test silently depends on the LLM alone.
_SOCIAL_PREMISE = (
    "Players must investigate a missing senator by questioning witnesses, "
    "checking alibis and chasing rumors in the city."
)
_SOCIAL_OPENING_ACTION = "I look around the marketplace to begin my investigation."


@allure.epic("AI Agent Orchestration")
@allure.feature("SceneBuilder real-model generation")
class TestSceneBuilderRealModel:
    @allure.story("Player-action landmark surfaces in scene")
    @allure.title("A real SceneBuilder model includes the player's named landmark in the scene")
    @pytest.mark.asyncio
    async def test_real_model_surfaces_landmark_from_player_action(self):
        game_state = director_helpers.make_game_state()
        # Switch the setting to coastal Alexandria so "lighthouse at Pharos"
        # is in-period and the model has no reason to refuse it.
        game_state.setting.region = "Egypt"
        game_state.setting.summary = "Ptolemaic Alexandria — bustling port, library, lighthouse of Pharos."

        builder = SceneBuilder(llm_client=real_llm_for("scene_builder"), language="English")

        scene = await builder.act(
            "I climb the stairs to the top of the lighthouse at Pharos and look out over the harbor.",
            {"game_state": game_state},
        )

        assert isinstance(scene, Scene)
        assert scene.description.strip(), "SceneBuilder returned empty description"
        # Input-tied: the player's distinctive landmark must surface in
        # the generated scene. Failure mode this catches: player_action
        # not interpolated into the prompt body.
        lower = scene.description.lower()
        assert any(keyword in lower for keyword in _LANDMARK_KEYWORDS), (
            "Scene description did not surface landmark {0!r}.\nDescription was:\n{1}".format(
                _LANDMARK_KEYWORDS,
                scene.description,
            )
        )

    @allure.story("Social-opening affordance injection")
    @allure.title("A real SceneBuilder produces a contact NPC for a social-investigation opening")
    @pytest.mark.asyncio
    async def test_real_model_provides_contact_for_social_opening(self):
        game_state = director_helpers.make_game_state()
        # Plant the social-premise markers SceneBuilder looks for so the
        # deterministic ``_ensure_social_opening_affordance`` post-step
        # is willing to fall back when the LLM forgets a contact.
        game_state.setting.summary = _SOCIAL_PREMISE

        builder = SceneBuilder(llm_client=real_llm_for("scene_builder"), language="English")
        scene = await builder.act(_SOCIAL_OPENING_ACTION, {"game_state": game_state})

        assert isinstance(scene, Scene)
        # Input-tied: a social-investigation opening must leave the player
        # with someone to talk to — either via the LLM populating
        # ``npcs_present`` directly or the deterministic Aurelia
        # fallback in ``_ensure_social_opening_affordance``. A truly
        # empty list signals the regression class the unit tests cover
        # but only with mocks.
        assert scene.npcs_present, "SceneBuilder produced no NPCs for a social opening"
        non_generic = [
            snpc
            for snpc in scene.npcs_present
            if isinstance(snpc, SceneNPC) and snpc.role.strip().lower() not in _GENERIC_SOCIAL_ROLES
        ]
        assert non_generic, (
            "SceneBuilder produced only generic bystanders for a social opening; roles were: {0}".format(
                [snpc.role for snpc in scene.npcs_present]
            )
        )
