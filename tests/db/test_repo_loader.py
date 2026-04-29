"""Tests for ``db.repo_loader.StateLoader`` against a real Postgres."""

from __future__ import annotations

import allure
import pytest
import sqlalchemy

from db import tables as tbl
from db.repo_loader_helpers import load_knowledge_graph
from knowledge.node import EdgeType, KnowledgeScope
from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


@allure.epic("Memory & Persistence")
@allure.feature("State loader")
class TestLoadEmpty:
    @allure.story("Empty state")
    @allure.title("load returns None when the session has no game_states row")
    @pytest.mark.asyncio
    async def test_returns_none_when_no_game(self, repo: GameRepository, test_session_id: str) -> None:
        loaded = await repo.load_game_state(test_session_id)
        assert loaded is None

    @allure.story("Empty state")
    @allure.title("load returns None when game_states exists but the settings row is missing")
    @pytest.mark.asyncio
    async def test_returns_none_when_setting_missing(
        self,
        repo: GameRepository,
        async_session,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        # Delete the settings row to simulate a mid-migration / orphaned state.
        await async_session.execute(
            sqlalchemy.delete(tbl.settings).where(tbl.settings.c.game_state_id == game_state.uuid),
        )

        loaded = await repo.load_game_state(test_session_id)
        assert loaded is None


@allure.epic("Memory & Persistence")
@allure.feature("State loader")
class TestLoadHappyPath:
    @allure.story("Happy path")
    @allure.title("load hydrates turn, round, player, locations, npcs, scene, and events")
    @pytest.mark.asyncio
    async def test_full_hydration_after_save(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        loaded = await repo.load_game_state(test_session_id)
        assert loaded is not None
        loaded_state, loaded_kg, loaded_events = loaded

        assert loaded_state.turn_count == game_state.turn_count
        assert loaded_state.round_number == game_state.round_number
        assert loaded_state.scene_number == game_state.scene_number
        assert loaded_state.game_time == game_state.game_time
        assert loaded_state.game_clock == pytest.approx(game_state.game_clock)
        assert len(loaded_state.locations) == len(game_state.locations)
        assert len(loaded_state.npcs) == len(game_state.npcs)
        assert loaded_state.current_scene is not None
        assert loaded_state.current_scene.description == game_state.current_scene.description
        assert len(loaded_events) == len(events)
        assert len(loaded_kg.all_nodes()) == len(kg.all_nodes())


@allure.epic("Memory & Persistence")
@allure.feature("State loader")
class TestLoadKnowledgeGraph:
    @allure.story("Knowledge graph")
    @allure.title("load_knowledge_graph returns an empty graph when no nodes exist")
    @pytest.mark.asyncio
    async def test_empty_graph_for_unknown_state(self, async_session) -> None:
        kg = await load_knowledge_graph(async_session, "00000000-0000-0000-0000-000000000000")
        assert kg.all_nodes() == []

    @allure.story("Knowledge graph")
    @allure.title("load_knowledge_graph reconstructs nodes and edges with correct EdgeType coercion")
    @pytest.mark.asyncio
    async def test_reconstructs_nodes_and_edges(
        self,
        repo: GameRepository,
        async_session,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        reloaded = await load_knowledge_graph(async_session, game_state.uuid)
        reloaded_nodes = reloaded.all_nodes()
        assert len(reloaded_nodes) == len(kg.all_nodes())
        scopes = {node.scope for node in reloaded_nodes}
        assert KnowledgeScope.CITY in scopes
        assert KnowledgeScope.LOCAL in scopes

        edge_types: set[EdgeType] = set()
        for node in reloaded_nodes:
            for _target, edge_type in reloaded.get_edges_from(node.uuid):
                edge_types.add(edge_type)
        assert EdgeType.TOLD_BY in edge_types
        assert EdgeType.TOLD_BY in edge_types
        assert EdgeType.WITNESSED in edge_types
