"""Tests for ``db.repo_admin.AdminQueries`` branches not covered by the mocked admin tests."""

from __future__ import annotations

import allure
import pytest

from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


@allure.epic("Memory & Persistence")
@allure.feature("Admin queries")
class TestSessionDetail:
    @allure.story("Session detail")
    @allure.title("get_session_detail returns None for an unknown session id")
    @pytest.mark.asyncio
    async def test_unknown_id_returns_none(self, repo: GameRepository) -> None:
        detail = await repo.admin.get_session_detail("00000000-0000-0000-0000-000000000000")
        assert detail is None

    @allure.story("Session detail")
    @allure.title("get_session_detail returns a dict with game_state=None when no game exists yet")
    @pytest.mark.asyncio
    async def test_session_without_game_returns_stub(
        self,
        repo: GameRepository,
        test_session_id: str,
    ) -> None:
        detail = await repo.admin.get_session_detail(test_session_id)
        assert detail is not None
        assert detail["game_state"] is None

    @allure.story("Session detail")
    @allure.title("get_session_detail returns populated counts when a full game state has been saved")
    @pytest.mark.asyncio
    async def test_session_with_game_populates_counts(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        detail = await repo.admin.get_session_detail(test_session_id)
        assert detail is not None
        assert detail["game_state"] is not None
        assert detail["location_count"] == len(game_state.locations)
        assert detail["npc_count"] == len(game_state.npcs)
        assert detail["knowledge_node_count"] == len(kg.all_nodes())
        assert detail["event_count"] == len(events)
        assert detail["setting"] is not None
        assert detail["player"] is not None


@allure.epic("Memory & Persistence")
@allure.feature("Admin queries")
class TestConversationLog:
    @allure.story("Conversation log")
    @allure.title("get_conversation_log returns an empty list when no game_state exists")
    @pytest.mark.asyncio
    async def test_empty_when_missing(self, repo: GameRepository, test_session_id: str) -> None:
        log = await repo.admin.get_conversation_log(test_session_id)
        assert log == []

    @allure.story("Conversation log")
    @allure.title("get_conversation_log returns the stored log for a saved game state")
    @pytest.mark.asyncio
    async def test_returns_stored_log(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        log = await repo.admin.get_conversation_log(test_session_id)
        assert log == game_state.conversation_log


@allure.epic("Memory & Persistence")
@allure.feature("Admin queries")
class TestKnowledgeGraph:
    @allure.story("Knowledge graph")
    @allure.title("get_knowledge_graph returns an empty skeleton when no game_state exists")
    @pytest.mark.asyncio
    async def test_empty_skeleton(self, repo: GameRepository, test_session_id: str) -> None:
        graph_payload = await repo.admin.get_knowledge_graph(test_session_id)
        assert graph_payload == {"nodes": [], "edges": []}

    @allure.story("Knowledge graph")
    @allure.title("get_knowledge_graph returns populated nodes and edges after a save")
    @pytest.mark.asyncio
    async def test_populated_graph(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        graph_payload = await repo.admin.get_knowledge_graph(test_session_id)
        assert len(graph_payload["nodes"]) == len(kg.all_nodes())
        assert len(graph_payload["edges"]) >= 3


@allure.epic("Memory & Persistence")
@allure.feature("Admin queries")
class TestWorldReads:
    @allure.story("World reads")
    @allure.title("get_npcs returns rows joined to the correct session")
    @pytest.mark.asyncio
    async def test_get_npcs(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        rows = await repo.admin.get_npcs(test_session_id)
        assert len(rows) == len(game_state.npcs)
        assert {row["name"] for row in rows} == {npc.name for npc in game_state.npcs.values()}

    @allure.story("World reads")
    @allure.title("get_locations returns rows joined to the correct session")
    @pytest.mark.asyncio
    async def test_get_locations(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        rows = await repo.admin.get_locations(test_session_id)
        assert len(rows) == len(game_state.locations)
        assert {row["name"] for row in rows} == {loc.name for loc in game_state.locations.values()}
