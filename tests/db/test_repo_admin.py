"""Tests for ``db.repo_admin.AdminQueries`` branches not covered by the mocked admin tests."""

from __future__ import annotations

import uuid as _uuid

import allure
import pytest

from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


def _chat_id() -> int:
    return int(_uuid.uuid4().int & 0x7FFFFFFF)


def _player_id() -> str:
    return str(_uuid.uuid4())


@allure.epic("Memory & Persistence")
@allure.feature("Admin queries")
class TestListSessionsFiltering:
    @allure.story("List sessions")
    @allure.title("list_sessions(web_player_id=...) returns rows ordered newest-first for that player")
    @pytest.mark.asyncio
    async def test_filters_to_web_player(self, repo: GameRepository) -> None:
        player_id = _player_id()
        other_player_id = _player_id()
        first = await repo.sessions.create_web(player_id)
        second = await repo.sessions.create_web(player_id)
        await repo.sessions.create_web(other_player_id)

        rows = await repo.admin.list_sessions(web_player_id=player_id)
        assert len(rows) == 2
        assert {str(row["web_player_id"]) for row in rows} == {player_id}
        # Newest-first ordering is load-bearing: admins looking at a player's
        # game history expect the most recent game to appear on top.
        assert [row["id"] for row in rows] == [second["id"], first["id"]]

    @allure.story("List sessions")
    @allure.title("list_sessions(telegram_chat_id=...) narrows to that chat's rows only")
    @pytest.mark.asyncio
    async def test_filters_to_telegram_chat(self, repo: GameRepository) -> None:
        chat_id = _chat_id()
        other_chat_id = _chat_id()
        await repo.sessions.create_telegram(chat_id)
        await repo.sessions.create_telegram(other_chat_id)

        rows = await repo.admin.list_sessions(telegram_chat_id=chat_id)
        assert len(rows) == 1
        assert rows[0]["telegram_chat_id"] == chat_id

    @allure.story("List sessions")
    @allure.title("list_sessions(search=<uuid prefix>) matches on sessions.id substring")
    @pytest.mark.asyncio
    async def test_search_matches_session_id_prefix(self, repo: GameRepository) -> None:
        row = await repo.sessions.create_telegram(_chat_id())
        await repo.sessions.create_telegram(_chat_id())
        prefix = str(row["id"])[:8]

        rows = await repo.admin.list_sessions(search=prefix)
        assert row["id"] in {item["id"] for item in rows}

    @allure.story("List sessions")
    @allure.title("list_sessions(search=<web_player_id substring>) matches on web_player_id")
    @pytest.mark.asyncio
    async def test_search_matches_web_player_id(self, repo: GameRepository) -> None:
        player_id = _player_id()
        created = await repo.sessions.create_web(player_id)
        await repo.sessions.create_web(_player_id())

        rows = await repo.admin.list_sessions(search=player_id[:12])
        assert created["id"] in {item["id"] for item in rows}

    @allure.story("List sessions")
    @allure.title("list_sessions(search=%) treats LIKE wildcards literally instead of matching everything")
    @pytest.mark.asyncio
    async def test_search_escapes_like_wildcards(self, repo: GameRepository) -> None:
        await repo.sessions.create_telegram(_chat_id())

        rows = await repo.admin.list_sessions(search="%")
        assert rows == []


@allure.epic("Memory & Persistence")
@allure.feature("Admin queries")
class TestNPCDetail:
    @allure.story("NPC detail")
    @allure.title("get_npc_detail returns None when the NPC belongs to a different session")
    @pytest.mark.asyncio
    async def test_wrong_session_returns_none(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)
        some_npc_id = next(iter(game_state.npcs))

        other_session = await repo.sessions.create_telegram(_chat_id())

        detail = await repo.admin.get_npc_detail(other_session["id"], some_npc_id)
        assert detail is None

    @allure.story("NPC detail")
    @allure.title("get_npc_detail returns the NPC row plus empty memory when no edges are registered")
    @pytest.mark.asyncio
    async def test_returns_npc_row_and_empty_memory(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)
        npc_id = next(iter(game_state.npcs))

        detail = await repo.admin.get_npc_detail(test_session_id, npc_id)
        assert detail is not None
        assert detail["npc"]["id"] == npc_id
        assert detail["memory_nodes"] == []
        assert detail["memory_edges"] == []


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
