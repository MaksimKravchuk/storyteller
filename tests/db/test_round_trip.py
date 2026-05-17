"""Cross-module integration tests: save → load → mutate → save → load."""

from __future__ import annotations

import uuid as uuid_mod

import allure
import pytest

from models.scene_action_log import ActorKind, SceneActionEntry
from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


@allure.epic("Memory & Persistence")
@allure.feature("Round trip")
class TestSaveLoadRoundTrip:
    @allure.story("Save and load")
    @allure.title("Full save then load reconstructs deep GameState equality on key fields")
    @pytest.mark.asyncio
    async def test_full_round_trip(
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
        assert loaded_state.conversation_log == game_state.conversation_log
        assert loaded_state.scene_conversation_log == game_state.scene_conversation_log

        assert loaded_state.setting.name == game_state.setting.name
        assert loaded_state.setting.time_period == game_state.setting.time_period

        assert set(loaded_state.locations.keys()) == set(game_state.locations.keys())
        assert set(loaded_state.npcs.keys()) == set(game_state.npcs.keys())

        assert loaded_state.player.known_npcs == game_state.player.known_npcs
        assert loaded_state.player.player_event_log == game_state.player.player_event_log
        assert loaded_state.player.learned_facts == game_state.player.learned_facts

        assert loaded_state.current_scene is not None
        assert loaded_state.current_scene.uuid == game_state.current_scene.uuid
        assert loaded_state.current_scene.location_id == game_state.current_scene.location_id

        assert {ev.name for ev in loaded_events} == {ev.name for ev in events}
        assert len(loaded_kg.all_nodes()) == len(kg.all_nodes())


@allure.epic("Memory & Persistence")
@allure.feature("Round trip")
class TestMutationIdempotence:
    @allure.story("Idempotent mutation")
    @allure.title("Save → mutate → save → load persists the mutation without leaving stale rows")
    @pytest.mark.asyncio
    async def test_mutation_idempotence(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        game_state.turn_count = 99
        game_state.game_time = "night"
        original_npc_count = len(game_state.npcs)
        drop_uuid = next(iter(game_state.npcs))
        game_state.npcs.pop(drop_uuid)

        await repo.save_game_state(test_session_id, game_state, kg, events)

        loaded = await repo.load_game_state(test_session_id)
        assert loaded is not None
        loaded_state, _loaded_kg, _loaded_events = loaded
        assert loaded_state.turn_count == 99
        assert loaded_state.game_time == "night"
        assert len(loaded_state.npcs) == original_npc_count - 1
        assert drop_uuid not in loaded_state.npcs


@allure.epic("Memory & Persistence")
@allure.feature("Round trip")
class TestNativeUuidRoundTrip:
    """Pin that, after save/load, uuid-keyed dicts hold native ``uuid.UUID`` objects."""

    @allure.story("Native UUID")
    @allure.title("Loaded GameState carries uuid.UUID instances on every uuid field and dict key")
    @pytest.mark.asyncio
    async def test_uuid_round_trip_is_native(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        await repo.save_game_state(test_session_id, game_state, kg, events)

        loaded = await repo.load_game_state(test_session_id)
        assert loaded is not None
        loaded_state, _kg, _events = loaded

        assert isinstance(loaded_state.uuid, uuid_mod.UUID)
        for npc_uuid, npc in loaded_state.npcs.items():
            assert isinstance(npc_uuid, uuid_mod.UUID)
            assert isinstance(npc.uuid, uuid_mod.UUID)
        for loc_uuid, loc in loaded_state.locations.items():
            assert isinstance(loc_uuid, uuid_mod.UUID)
            assert isinstance(loc.uuid, uuid_mod.UUID)
        for known in loaded_state.player.known_npcs:
            assert isinstance(known, uuid_mod.UUID)


@allure.epic("Memory & Persistence")
@allure.feature("Round trip")
class TestSceneActionLogRoundTrip:
    """Pin that the new ``scene_action_log`` JSONB column survives save/load.

    The model-only round-trip proves Pydantic works; this proves the
    repo serializer (``model_dump(mode="json")``) and hydrator
    (``SceneActionEntry(**raw)``) consume it correctly — including the
    native ``uuid.UUID`` actor/target fields and the ``ActorKind`` enum
    through actual asyncpg JSONB.
    """

    @allure.story("Scene action log")
    @allure.title("scene_action_log survives save/load with native UUID fields and ActorKind enum intact")
    @pytest.mark.asyncio
    async def test_scene_action_log_round_trip(
        self,
        repo: GameRepository,
        populated_game_state,
        test_session_id: str,
    ) -> None:
        game_state, kg, events = populated_game_state
        actor_uuid = next(iter(game_state.npcs))
        target_uuid = uuid_mod.uuid4()
        game_state.scene_action_log = [
            SceneActionEntry(
                actor_kind=ActorKind.NPC,
                actor_uuid=actor_uuid,
                actor_name="Marcus",
                action_type="ATTACK",
                description="Marcus lunges with a dagger.",
                target_uuid=target_uuid,
                target_name="Livia",
                game_clock=3.5,
                significant=True,
                metadata={"contest_outcome": "actor_wins"},
            ),
            SceneActionEntry(
                actor_kind=ActorKind.EVENT,
                actor_name="",
                action_type="COMBAT_WITNESS",
                description="A clash erupts by the well.",
                game_clock=3.6,
                significant=True,
                metadata={"already_persisted": True, "witness_ids": [str(actor_uuid)]},
            ),
        ]

        await repo.save_game_state(test_session_id, game_state, kg, events)
        loaded = await repo.load_game_state(test_session_id)
        assert loaded is not None
        loaded_state, _kg, _events = loaded

        npc_entry, event_entry = loaded_state.scene_action_log
        assert isinstance(npc_entry.actor_kind, ActorKind)
        assert npc_entry.actor_kind == ActorKind.NPC
        assert isinstance(npc_entry.actor_uuid, uuid_mod.UUID)
        assert npc_entry.actor_uuid == actor_uuid
        assert isinstance(npc_entry.target_uuid, uuid_mod.UUID)
        assert npc_entry.target_uuid == target_uuid
        assert npc_entry.game_clock == pytest.approx(3.5)
        assert npc_entry.significant is True
        assert npc_entry.metadata == {"contest_outcome": "actor_wins"}

        assert event_entry.actor_kind == ActorKind.EVENT
        assert event_entry.actor_uuid is None
        assert event_entry.metadata["already_persisted"] is True
        assert event_entry.metadata["witness_ids"] == [str(actor_uuid)]
