"""Tests for ``db.repo_admin.AdminQueries`` branches not covered by the mocked admin tests."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

import allure
import pytest
from sqlalchemy import insert, select

from db import tables as tbl
from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


def _chat_id() -> int:
    return int(_uuid.uuid4().int & 0x7FFFFFFF)


def _player_id() -> str:
    return str(_uuid.uuid4())


async def _create_account(async_session, email: str) -> dict:
    account_rows = await async_session.execute(
        insert(tbl.accounts).values(supabase_user_id=str(_uuid.uuid4()), email=email).returning(tbl.accounts),
    )
    return dict(account_rows.mappings().one())


async def _game_id_for_session(async_session, session_id: str) -> str:
    """Return the game_states.id row created by save_game_state for a session."""
    result = await async_session.execute(
        select(tbl.game_states.c.id).where(tbl.game_states.c.session_id == session_id),
    )
    return str(result.scalar_one())


async def _insert_feedback(async_session, *, fields: dict) -> None:
    """Insert a feedback row from a values dict (bypasses repo to control created_at)."""
    await async_session.execute(insert(tbl.beta_feedback).values(**fields))


async def _log_ai_call(repo: GameRepository, session_id: str, user_id: str, prompt: int, completion: int) -> None:
    await repo.ai_logs.save(
        [
            {
                "session_id": session_id,
                "agent_name": "Director",
                "model": "gpt-test",
                "system_prompt": "system",
                "messages": [],
                "response_content": "response",
                "prompt_tokens": prompt,
                "completion_tokens": completion,
            },
        ],
        turn_number=1,
        user_id=user_id,
    )


async def _create_account_pair(async_session) -> tuple[dict, dict]:
    account = await _create_account(async_session, "player@example.com")
    other_account = await _create_account(async_session, "other@example.com")
    return account, other_account


async def _create_list_user_sessions(repo: GameRepository, account: dict, other_account: dict) -> tuple[dict, dict]:
    first = await repo.sessions.create_web(str(account["id"]))
    second = await repo.sessions.create_web(str(account["id"]))
    await repo.sessions.create_web(str(other_account["id"]))
    return first, second


async def _log_list_user_calls(repo: GameRepository, account: dict, first: dict, second: dict) -> None:
    await _log_ai_call(repo, first["id"], str(account["id"]), 10, 3)
    await _log_ai_call(repo, second["id"], str(account["id"]), 7, 2)


async def _create_user_detail_sessions(
    repo: GameRepository,
    account: dict,
    other_account: dict,
) -> tuple[dict, dict]:
    owned = await repo.sessions.create_web(str(account["id"]))
    other = await repo.sessions.create_web(str(other_account["id"]))
    return owned, other


async def _log_user_detail_calls(
    repo: GameRepository,
    account: dict,
    other_account: dict,
    owned: dict,
    other: dict,
) -> None:
    await _log_ai_call(repo, owned["id"], str(account["id"]), 11, 4)
    await _log_ai_call(repo, other["id"], str(other_account["id"]), 100, 50)


async def _seed_account_with_saved_game(
    repo: GameRepository,
    async_session,
    populated_game_state,
    email: str,
) -> tuple[dict, str]:
    """Seed an account, web session, and saved game state; return (account, game_id)."""
    account = await _create_account(async_session, email)
    session_row = await repo.sessions.create_web(str(account["id"]))
    game_state, kg, events = populated_game_state
    await repo.save_game_state(session_row["id"], game_state, kg, events)
    game_id = await _game_id_for_session(async_session, session_row["id"])
    return account, game_id


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

    @allure.story("List sessions")
    @allure.title("list_sessions joins the owning account's email and id when web_player_id matches")
    @pytest.mark.asyncio
    async def test_list_sessions_joins_account_email(
        self,
        repo: GameRepository,
        async_session,
    ) -> None:
        account = await _create_account(async_session, "owner@example.com")
        created = await repo.sessions.create_web(str(account["id"]))

        rows = await repo.admin.list_sessions(web_player_id=str(account["id"]))
        match = next(row for row in rows if row["id"] == created["id"])
        assert match["account_email"] == "owner@example.com"
        assert str(match["account_id"]) == str(account["id"])

    @allure.story("List sessions")
    @allure.title("list_sessions returns null account fields for sessions whose web_player_id has no matching account")
    @pytest.mark.asyncio
    async def test_list_sessions_account_email_null_for_orphan_session(
        self,
        repo: GameRepository,
    ) -> None:
        orphan_player_id = _player_id()
        created = await repo.sessions.create_web(orphan_player_id)

        rows = await repo.admin.list_sessions(web_player_id=orphan_player_id)
        match = next(row for row in rows if row["id"] == created["id"])
        assert match["account_id"] is None
        assert match["account_email"] is None

    @allure.story("List sessions")
    @allure.title("list_sessions returns null account fields for telegram-only sessions")
    @pytest.mark.asyncio
    async def test_list_sessions_telegram_session_returns_null_account(
        self,
        repo: GameRepository,
    ) -> None:
        chat_id = _chat_id()
        created = await repo.sessions.create_telegram(chat_id)

        rows = await repo.admin.list_sessions(telegram_chat_id=chat_id)
        match = next(row for row in rows if row["id"] == created["id"])
        assert match["telegram_chat_id"] == chat_id
        assert match["account_id"] is None
        assert match["account_email"] is None


@allure.epic("Memory & Persistence")
@allure.feature("Admin queries")
class TestUserManagement:
    @allure.story("User list")
    @allure.title("list_users returns accounts with session counts and aggregate AI usage")
    @pytest.mark.asyncio
    async def test_list_users_includes_session_and_usage_totals(self, repo: GameRepository, async_session) -> None:
        account, other_account = await _create_account_pair(async_session)
        first, second = await _create_list_user_sessions(repo, account, other_account)
        await _log_list_user_calls(repo, account, first, second)

        rows = await repo.admin.list_users()
        user_row = next(row for row in rows if row["id"] == account["id"])

        assert user_row["email"] == "player@example.com"
        assert user_row["session_count"] == 2
        assert user_row["call_count"] == 2
        assert user_row["prompt_tokens"] == 17
        assert user_row["completion_tokens"] == 5
        assert user_row["total_tokens"] == 22

    @allure.story("User detail")
    @allure.title("get_user_detail returns account, usage totals, and sessions for only that account")
    @pytest.mark.asyncio
    async def test_get_user_detail_includes_only_that_accounts_sessions(
        self,
        repo: GameRepository,
        async_session,
        populated_game_state,
    ) -> None:
        account, other_account = await _create_account_pair(async_session)
        owned, other = await _create_user_detail_sessions(repo, account, other_account)
        game_state, knowledge_graph, events = populated_game_state
        await repo.save_game_state(owned["id"], game_state, knowledge_graph, events)
        await _log_user_detail_calls(repo, account, other_account, owned, other)

        detail = await repo.admin.get_user_detail(str(account["id"]))

        assert detail is not None
        assert detail["account"]["id"] == account["id"]
        assert detail["usage"]["call_count"] == 1
        assert detail["usage"]["total_tokens"] == 15
        assert [session["id"] for session in detail["sessions"]] == [owned["id"]]
        assert detail["sessions"][0]["call_count"] == 1
        assert detail["sessions"][0]["total_tokens"] == 15
        assert detail["sessions"][0]["conversation_log"] == [{"speaker": "player", "text": "hello"}]
        assert detail["sessions"][0]["scene_conversation_log"] == [{"speaker": "merchant", "text": "welcome"}]
        assert detail["sessions"][0]["scene_action_log"] == []

    @allure.story("User detail")
    @allure.title("get_user_detail returns None for an unknown account id")
    @pytest.mark.asyncio
    async def test_get_user_detail_unknown_user_returns_none(self, repo: GameRepository) -> None:
        detail = await repo.admin.get_user_detail("00000000-0000-0000-0000-000000000000")
        assert detail is None

    @allure.story("User list")
    @allure.title("list_users(email_query=...) returns only accounts whose email matches the substring")
    @pytest.mark.asyncio
    async def test_list_users_email_query_filters_substring(self, repo: GameRepository, async_session) -> None:
        alice = await _create_account(async_session, "alice@example.com")
        await _create_account(async_session, "bob@example.com")

        rows = await repo.admin.list_users(email_query="ali")
        emails = {row["email"] for row in rows}
        assert emails == {"alice@example.com"}
        assert str(rows[0]["id"]) == str(alice["id"])

    @allure.story("User list")
    @allure.title("list_users(email_query=%) escapes LIKE wildcards literally instead of matching everything")
    @pytest.mark.asyncio
    async def test_list_users_email_query_escapes_like_wildcards(self, repo: GameRepository, async_session) -> None:
        await _create_account(async_session, "alice@example.com")

        rows = await repo.admin.list_users(email_query="%")
        assert rows == []

    @allure.story("User detail")
    @allure.title("get_user_detail includes invites matching the account's email")
    @pytest.mark.asyncio
    async def test_get_user_detail_includes_invites_for_email(
        self,
        repo: GameRepository,
        async_session,
    ) -> None:
        account = await _create_account(async_session, "invitee@example.com")
        await async_session.execute(
            insert(tbl.beta_invites).values(email="invitee@example.com", status="invited"),
        )

        detail = await repo.admin.get_user_detail(str(account["id"]))

        assert detail is not None
        assert len(detail["invites"]) == 1
        assert detail["invites"][0]["email"] == "invitee@example.com"
        assert detail["invites"][0]["status"] == "invited"
        assert detail["invites"][0]["invited_at"] is not None

    @allure.story("User detail")
    @allure.title("get_user_detail returns empty invites list when no invite exists for the email")
    @pytest.mark.asyncio
    async def test_get_user_detail_invites_empty_when_no_match(
        self,
        repo: GameRepository,
        async_session,
    ) -> None:
        account = await _create_account(async_session, "no-invite@example.com")

        detail = await repo.admin.get_user_detail(str(account["id"]))

        assert detail is not None
        assert detail["invites"] == []

    @allure.story("User detail")
    @allure.title("get_user_detail includes feedback rows submitted by this account, newest first")
    @pytest.mark.asyncio
    async def test_get_user_detail_includes_feedback_for_user_id(
        self,
        repo: GameRepository,
        async_session,
        populated_game_state,
    ) -> None:
        account, game_id = await _seed_account_with_saved_game(
            repo,
            async_session,
            populated_game_state,
            "fb@example.com",
        )
        # Explicit created_at: same-transaction func.now() would tie and obscure DESC ordering.
        older = datetime(2025, 1, 1, tzinfo=timezone.utc)
        newer = datetime(2025, 6, 1, tzinfo=timezone.utc)
        common = {"user_id": account["id"], "game_id": game_id}
        await _insert_feedback(
            async_session, fields={**common, "category": "bug", "message": "first", "created_at": older}
        )
        await _insert_feedback(
            async_session,
            fields={**common, "category": "praise", "message": "second", "created_at": newer},
        )

        detail = await repo.admin.get_user_detail(str(account["id"]))

        assert detail is not None
        assert len(detail["feedback"]) == 2
        # Newest-first ordering is load-bearing for admin review.
        assert [row["message"] for row in detail["feedback"]] == ["second", "first"]
        assert detail["feedback"][0]["category"] == "praise"


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

    @allure.story("Session detail")
    @allure.title("get_session_detail surfaces the owning account's email when web_player_id matches")
    @pytest.mark.asyncio
    async def test_get_session_detail_joins_account_email(
        self,
        repo: GameRepository,
        async_session,
    ) -> None:
        account = await _create_account(async_session, "owner@example.com")
        created = await repo.sessions.create_web(str(account["id"]))

        detail = await repo.admin.get_session_detail(created["id"])

        assert detail is not None
        assert detail["session"]["account_email"] == "owner@example.com"
        assert str(detail["session"]["account_id"]) == str(account["id"])


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
