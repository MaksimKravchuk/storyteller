"""Tests for ``db.repo_saver.StateSaver`` against a real Postgres."""

from __future__ import annotations

import allure
import pytest
import sqlalchemy

from db import tables as tbl
from knowledge.graph import KnowledgeGraph
from knowledge.node import EdgeType, KnowledgeNode
from models.game_state import GameState
from models.scene import Scene
from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


async def _count(async_session, table, game_state_id: str) -> int:
    base = sqlalchemy.select(sqlalchemy.func.count()).select_from(table)
    query = await async_session.execute(base.where(table.c.game_state_id == game_state_id))
    return query.scalar() or 0


async def _child_counts(async_session, game_state_id: str) -> dict:
    return {
        "locations": await _count(async_session, tbl.locations, game_state_id),
        "npcs": await _count(async_session, tbl.npcs, game_state_id),
        "events": await _count(async_session, tbl.game_events, game_state_id),
        "nodes": await _count(async_session, tbl.knowledge_nodes, game_state_id),
    }


@allure.epic("Memory & Persistence")
@allure.feature("State saver")
class TestFreshSave:
    @allure.story("Insert")
    @allure.title("A first save inserts a game_states row plus all child rows")
    @pytest.mark.asyncio
    async def test_fresh_save_inserts_all_children(
        self,
        repo: GameRepository,
        async_session,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        gs_query = await async_session.execute(
            sqlalchemy.select(tbl.game_states).where(tbl.game_states.c.id == game_state.uuid),
        )
        gs_row = gs_query.mappings().first()
        assert gs_row is not None
        assert gs_row["turn_count"] == game_state.turn_count

        counts = await _child_counts(async_session, game_state.uuid)
        assert counts["locations"] == len(game_state.locations)
        assert counts["npcs"] == len(game_state.npcs)
        assert counts["events"] == len(events)
        assert counts["nodes"] == len(kg.all_nodes())


@allure.epic("Memory & Persistence")
@allure.feature("State saver")
class TestUpsertMutation:
    @allure.story("Upsert")
    @allure.title("A second save with mutated state updates the existing game_states row")
    @pytest.mark.asyncio
    async def test_second_save_upserts_row(
        self,
        repo: GameRepository,
        async_session,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)
        game_state.turn_count = 42
        game_state.game_time = "evening"
        await repo.save_game_state(test_session_id, game_state, kg, events)

        row_result = await async_session.execute(
            sqlalchemy.select(tbl.game_states).where(tbl.game_states.c.id == game_state.uuid),
        )
        mutated = row_result.mappings().one()
        assert mutated["turn_count"] == 42
        assert mutated["game_time"] == "evening"


@allure.epic("Memory & Persistence")
@allure.feature("State saver")
class TestReplaceRows:
    @allure.story("Replace rows")
    @allure.title("replace_rows deletes stale children when saves shrink the collection")
    @pytest.mark.asyncio
    async def test_shrinking_locations(
        self,
        repo: GameRepository,
        async_session,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)
        assert await _count(async_session, tbl.locations, game_state.uuid) == len(game_state.locations)

        kept_uuid = next(iter(game_state.locations))
        game_state.locations = {kept_uuid: game_state.locations[kept_uuid]}
        await repo.save_game_state(test_session_id, game_state, kg, events)

        assert await _count(async_session, tbl.locations, game_state.uuid) == 1


@allure.epic("Memory & Persistence")
@allure.feature("State saver")
class TestSceneHistory:
    @allure.story("Scene history")
    @allure.title("Saving a new current scene marks the previous one is_current=False")
    @pytest.mark.asyncio
    async def test_previous_scene_becomes_historical(
        self,
        repo: GameRepository,
        async_session,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        first_scene_uuid = game_state.current_scene.uuid
        await repo.save_game_state(test_session_id, game_state, kg, events)

        new_scene = Scene(
            location_id=game_state.current_scene.location_id,
            description="Later that afternoon",
            ambient_description="Shadows lengthen.",
            time_of_day="afternoon",
        )
        game_state.current_scene = new_scene
        game_state.scene_number = 2
        await repo.save_game_state(test_session_id, game_state, kg, events)

        scene_rows = await async_session.execute(
            sqlalchemy.select(tbl.scenes).where(tbl.scenes.c.game_state_id == game_state.uuid),
        )
        rows = list(scene_rows.mappings())
        assert len(rows) == 2
        current_flags = {row["id"]: row["is_current"] for row in rows}
        assert current_flags[first_scene_uuid] is False
        assert current_flags[new_scene.uuid] is True


@allure.epic("Memory & Persistence")
@allure.feature("State saver")
class TestEdgeTypeRoundTrip:
    @allure.story("Knowledge edges")
    @allure.title("_save_knowledge round-trips every EdgeType enum value without loss")
    @pytest.mark.asyncio
    async def test_every_edge_type_persists(
        self,
        repo: GameRepository,
        async_session,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, _kg, events = populated_game_state
        kg = KnowledgeGraph()
        root = KnowledgeNode(text="root")
        kg.add_node(root)
        edge_targets: dict[str, EdgeType] = {}
        for edge_type in EdgeType:
            leaf = KnowledgeNode(text="leaf-{0}".format(edge_type.value))
            kg.add_node(leaf)
            kg.add_edge(root.uuid, leaf.uuid, edge_type)
            edge_targets[leaf.uuid] = edge_type
        game_state.knowledge_graph = kg
        await repo.save_game_state(test_session_id, game_state, kg, events)

        rows_query = await async_session.execute(
            sqlalchemy.select(tbl.knowledge_edges).where(
                tbl.knowledge_edges.c.game_state_id == game_state.uuid,
            ),
        )
        loaded = {row["to_node_id"]: row["edge_type"] for row in rows_query.mappings()}
        for leaf_uuid, edge_type in edge_targets.items():
            assert loaded[leaf_uuid] == edge_type.value

    @allure.story("GameState reuse")
    @allure.title("Builder game_state fixture can be saved twice with no row duplication")
    @pytest.mark.asyncio
    async def test_idempotent_save_no_duplicates(
        self,
        repo: GameRepository,
        async_session,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        assert isinstance(game_state, GameState)
        await repo.save_game_state(test_session_id, game_state, kg, events)
        await repo.save_game_state(test_session_id, game_state, kg, events)

        assert await _count(async_session, tbl.locations, game_state.uuid) == len(game_state.locations)
        assert await _count(async_session, tbl.npcs, game_state.uuid) == len(game_state.npcs)
