"""Tests for scene tracking: scene_number in conversation log, scene converter, and admin route."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from db.converters.scene import scene_to_row
from models.scene import Scene, SceneNPC
from tests.director_helpers import make_director, make_game_state

_TALK = "TALK"
_MOVE = "MOVE"
_NARRATOR = "narrator"
_SCENE_NUM = "scene_number"


def _route(action_type, *, delegate=(_NARRATOR,)):
    return {
        "action_type": action_type,
        "targets": [],
        "needs_clarification": False,
        "delegate_to": delegate,
    }


class TestSceneNumberInConversationLog:
    """conversation_log entries must include scene_number."""

    @pytest.mark.asyncio
    async def test_scene_number_in_log_entry(self):
        director = make_director(route_response=_route(_TALK))
        await director.act("hello")
        log = director._deps.game_state.conversation_log
        assert len(log) == 1
        assert _SCENE_NUM in log[0]
        assert log[0][_SCENE_NUM] == 0

    @pytest.mark.asyncio
    async def test_scene_number_increments_on_move(self):
        gs = make_game_state()
        director = make_director(game_state=gs, route_response=_route(_MOVE))
        await director.act("go north")
        log = gs.conversation_log
        assert len(log) == 1
        assert log[0][_SCENE_NUM] == 1

    @pytest.mark.asyncio
    async def test_multiple_turns_same_scene(self):
        gs = make_game_state()
        director = make_director(game_state=gs, route_response=_route(_TALK))
        await director.act("hello")
        await director.act("what news?")
        assert gs.conversation_log[0][_SCENE_NUM] == 0
        assert gs.conversation_log[1][_SCENE_NUM] == 0

    @pytest.mark.asyncio
    async def test_scene_number_across_scenes(self):
        gs = make_game_state()

        director_talk = make_director(game_state=gs, route_response=_route(_TALK))
        await director_talk.act("hello")
        assert gs.conversation_log[0][_SCENE_NUM] == 0

        director_move = make_director(game_state=gs, route_response=_route(_MOVE))
        await director_move.act("go north")
        assert gs.conversation_log[1][_SCENE_NUM] == 1

        director_talk2 = make_director(game_state=gs, route_response=_route(_TALK))
        await director_talk2.act("look around")
        assert gs.conversation_log[2][_SCENE_NUM] == 1


class TestSceneToRowConverter:
    """scene_to_row must include scene_number."""

    def test_default_scene_number_zero(self):
        scene = Scene(location_id="market", description="A market.")
        row = scene_to_row(scene, "gs-1")
        assert row[_SCENE_NUM] == 0

    def test_explicit_scene_number(self):
        scene = Scene(location_id="docks", description="The docks.")
        row = scene_to_row(scene, "gs-1", is_current=True, scene_number=3)
        assert row[_SCENE_NUM] == 3
        assert row["is_current"] is True

    def test_row_has_scene_and_location_keys(self):
        scene = Scene(
            location_id="forum",
            description="The forum.",
            npcs_present=[SceneNPC(role="guard")],
            points_of_interest=["fountain"],
        )
        row = scene_to_row(scene, "gs-1", scene_number=1)
        expected = {"id", "game_state_id", _SCENE_NUM, "location_id", "npcs_present"}
        assert expected.issubset(row.keys())


class TestAdminScenesRoute:
    """Admin server must register the /scenes endpoint."""

    def test_scenes_route_registered(self):
        from interfaces.admin import AdminServer

        server = AdminServer(MagicMock(), port=0)
        route_paths = []
        for route in server._app.router.routes():
            if hasattr(route, "resource"):
                route_paths.append(route.resource.canonical)
        assert "/api/sessions/{id}/scenes" in route_paths
