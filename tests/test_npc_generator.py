"""Tests for cast.npc_generator.NPCGenerator — batch NPC card generation and context caps."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast._scene_location import UNKNOWN_SCENE_LOCATION
from cast.npc_generator import NPCGenerator
from cast.schemas.npc_response import NPCAttributes, NPCResponse
from db.converters import npc as npc_conv
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from tests._uuid_helpers import make_uuid

_GHOST_LOCATION_TEXT = str(UNKNOWN_SCENE_LOCATION)

_SEND_JSON = "_send_json"
_SETTING_CAP = 1500
_SCENE_CAP = 200
_SOCIAL_CAP = 800


def _full_npc_payload(name: str) -> NPCResponse:
    return NPCResponse(
        name=name,
        biography="{0} bio".format(name),
        appearance="tall",
        short_descriptor="a tall figure in plain cloth",
        occupation="guard",
        personality_traits=["stern"],
        speech_style="gruff",
        knowledge_scope="city",
        attributes=NPCAttributes(combat_skill=7),
        inventory=["sword"],
    )


@allure.epic("NPC Interaction")
@allure.feature("NPC Generator")
class TestNPCGenerator:
    @allure.story("Batch generation")
    @allure.title("NPCGenerator produces one NPCCard per requested role with all fields populated")
    @pytest.mark.asyncio
    async def test_one_card_per_request(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        payloads = [_full_npc_payload("Aulus"), _full_npc_payload("Brutus")]
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=payloads)):
            cards = await gen.act(["guard", "merchant"], {"game_state": game_state})
        assert len(cards) == 2
        assert all(isinstance(card, NPCCard) for card in cards)
        assert cards[0].name == "Aulus"
        assert cards[0].biography == "Aulus bio"
        assert cards[0].personality_traits == ["stern"]

    @allure.story("Batch generation")
    @allure.title("NPCGenerator defaults every missing LLM field including occupation from the request string")
    @pytest.mark.asyncio
    async def test_missing_fields_defaulted(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[NPCResponse()])):
            cards = await gen.act(["tavern keeper"], {"game_state": game_state})
        card = cards[0]
        assert card.name == "Unknown"
        assert card.biography == ""
        assert card.occupation == "tavern keeper"
        assert card.personality_traits == []
        assert card.speech_style == "neutral"
        assert card.knowledge_scope == "local"
        assert card.attributes == NPCAttributes().model_dump()
        assert card.inventory == []

    @allure.story("Location propagation")
    @allure.title("NPCGenerator stamps each card with the current scene's location_id from game state")
    @pytest.mark.asyncio
    async def test_location_propagation(self, game_state) -> None:
        forum_id = make_uuid("forum")
        game_state.current_scene = Scene(location_id=forum_id, description="plaza")
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("Caius")])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        assert cards[0].location_id == forum_id

    @allure.story("Location propagation")
    @allure.title("NPCGenerator falls back to the player's location when the scene's location is the unknown sentinel")
    @pytest.mark.asyncio
    async def test_unknown_scene_location_falls_back_to_player(self, game_state) -> None:
        forum_id = make_uuid("forum")
        game_state.player.location_id = forum_id
        game_state.current_scene = Scene(location_id=UNKNOWN_SCENE_LOCATION, description="plaza")
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("Caius")])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        assert cards[0].location_id == forum_id
        assert cards[0].location_id != UNKNOWN_SCENE_LOCATION

    @allure.story("Location propagation")
    @allure.title(
        "NPCGenerator returns location_id=None when the scene is the unknown sentinel and the player has no location"
    )
    @pytest.mark.asyncio
    async def test_unknown_scene_with_no_player_location(self, game_state) -> None:
        game_state.player.location_id = None
        game_state.current_scene = Scene(location_id=UNKNOWN_SCENE_LOCATION, description="plaza")
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("Caius")])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        assert cards[0].location_id is None
        assert cards[0].location_id != UNKNOWN_SCENE_LOCATION

    @allure.story("Location propagation")
    @allure.title(
        "NPCGenerator persists a non-sentinel location_id through npc_to_row, never leaking the ghost UUID string"
    )
    @pytest.mark.asyncio
    async def test_persisted_npc_row_never_carries_ghost_uuid(self, game_state) -> None:
        forum_id = make_uuid("forum")
        game_state.player.location_id = forum_id
        game_state.current_scene = Scene(location_id=UNKNOWN_SCENE_LOCATION, description="plaza")
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("Caius")])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        row = npc_conv.npc_to_row(cards[0], "game-state-id")
        assert row["location_id"] != _GHOST_LOCATION_TEXT
        assert row["location_id"] == str(forum_id)

    @allure.story("Location propagation")
    @allure.title("NPCGenerator leaves location_id None when the game state has no current scene")
    @pytest.mark.asyncio
    async def test_location_none_when_no_scene(self, game_state) -> None:
        game_state.current_scene = None
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("Drusus")])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        assert cards[0].location_id is None

    @allure.story("Location propagation")
    @allure.title(
        "NPCGenerator stamps the player's location when no current scene is set but the player has a location"
    )
    @pytest.mark.asyncio
    async def test_no_scene_with_player_location_uses_player(self, game_state) -> None:
        forum_id = make_uuid("forum")
        game_state.player.location_id = forum_id
        game_state.current_scene = None
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("Drusus")])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        assert cards[0].location_id == forum_id

    @allure.story("Batch generation")
    @allure.title("NPCGenerator preserves input order when generating NPCs sequentially")
    @pytest.mark.asyncio
    async def test_sequential_preserves_order(self, game_state) -> None:
        names = ["One", "Two", "Three", "Four", "Five"]
        payloads = [_full_npc_payload(n) for n in names]
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=payloads)):
            cards = await gen.act(names, {"game_state": game_state})
        assert [card.name for card in cards] == names

    @allure.story("Duplicate prevention")
    @allure.title("NPCGenerator accumulates forbidden_names so each serial call sees earlier picks (KER-25)")
    @pytest.mark.asyncio
    async def test_forbidden_names_accumulate_across_batch(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        payloads = [_full_npc_payload("Aulus"), _full_npc_payload("Brutus"), _full_npc_payload("Caius")]
        send_json = AsyncMock(side_effect=payloads)
        with patch.object(gen, _SEND_JSON, new=send_json):
            await gen.act(["guard", "guard", "guard"], {"game_state": game_state})
        prompts = [call.args[0] for call in send_json.await_args_list]
        assert "Aulus" not in prompts[0]
        assert "Aulus" in prompts[1]
        assert "Aulus" in prompts[2]
        assert "Brutus" in prompts[2]

    @allure.story("Duplicate prevention")
    @allure.title("NPCGenerator disambiguates when the LLM returns a duplicate name within a batch (KER-25)")
    @pytest.mark.asyncio
    async def test_within_batch_duplicate_is_renamed(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        payloads = [_full_npc_payload("Фрол Михайлов"), _full_npc_payload("Фрол Михайлов")]
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=payloads)):
            cards = await gen.act(["fisherman", "cooper"], {"game_state": game_state})
        assert cards[0].name == "Фрол Михайлов"
        assert cards[1].name != cards[0].name
        assert "Фрол Михайлов" in cards[1].name

    @allure.story("Duplicate prevention")
    @allure.title("NPCGenerator appends numeric suffix when three cards collide on the same name")
    @pytest.mark.asyncio
    async def test_triple_collision_uses_numeric_suffix(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        payloads = [_full_npc_payload("Фрол Михайлов") for _ in range(3)]
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=payloads)):
            cards = await gen.act(["fisherman", "cooper", "smith"], {"game_state": game_state})
        assert cards[0].name == "Фрол Михайлов"
        assert cards[1].name == "Фрол Михайлов (guard)"
        assert cards[2].name == "Фрол Михайлов (guard) [2]"

    @allure.story("Duplicate prevention")
    @allure.title("NPCGenerator forbids names of NPCs already in the current scene")
    @pytest.mark.asyncio
    async def test_existing_scene_npc_names_forbidden(self, game_state) -> None:
        existing = NPCCard(name="Ivan Matveyev", occupation="fisherman")
        game_state.npcs[existing.uuid] = existing
        game_state.current_scene = Scene(
            location_id=make_uuid("village"),
            description="wooden pier",
            npcs_present=[SceneNPC(role="fisherman", uuid=existing.uuid)],
        )
        gen = NPCGenerator(llm_client=MagicMock())
        send_json = AsyncMock(side_effect=[_full_npc_payload("Pyotr")])
        with patch.object(gen, _SEND_JSON, new=send_json):
            await gen.act(["guard"], {"game_state": game_state})
        rendered_prompt = send_json.await_args_list[0].args[0]
        assert "Ivan Matveyev" in rendered_prompt

    @allure.story("Duplicate prevention")
    @allure.title("NPCGenerator disambiguates when LLM echoes an already-present scene NPC's name")
    @pytest.mark.asyncio
    async def test_llm_collision_with_existing_scene_npc_is_renamed(self, game_state) -> None:
        existing = NPCCard(name="Фрол Михайлов", occupation="fisherman")
        game_state.npcs[existing.uuid] = existing
        game_state.current_scene = Scene(
            location_id=make_uuid("village"),
            description="wooden pier",
            npcs_present=[SceneNPC(role="fisherman", uuid=existing.uuid)],
        )
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("Фрол Михайлов")])):
            cards = await gen.act(["cooper"], {"game_state": game_state})
        assert cards[0].name != "Фрол Михайлов"
        assert "Фрол Михайлов" in cards[0].name

    @allure.story("Context truncation")
    @allure.title("NPCGenerator truncates setting summary, scene description, and social structure to their caps")
    @pytest.mark.asyncio
    async def test_context_truncation(self, game_state) -> None:
        game_state.setting.summary = "s" * 2000
        game_state.setting.social_structure = "h" * 1200
        game_state.current_scene = Scene(location_id=make_uuid("x"), description="d" * 1200)
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("X")])):
            await gen.act(["guard"], {"game_state": game_state})
        ctx = gen._system_prompt_vars
        assert len(ctx["setting_summary"]) == _SETTING_CAP
        assert len(ctx["location_name"]) == _SCENE_CAP
        assert len(ctx["social_structure"]) == _SOCIAL_CAP

    @allure.story("Context truncation")
    @allure.title("NPCGenerator labels the location as 'Unknown location' when no current scene is present")
    @pytest.mark.asyncio
    async def test_unknown_location_label(self, game_state) -> None:
        game_state.current_scene = None
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("X")])):
            await gen.act(["guard"], {"game_state": game_state})
        assert gen._system_prompt_vars["location_name"] == "Unknown location"

    @allure.story("Short descriptor")
    @allure.title("NPCGenerator copies short_descriptor from the LLM response onto each card")
    @pytest.mark.asyncio
    async def test_short_descriptor_copied(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        payload = _full_npc_payload("Aulus")
        payload.short_descriptor = "a stocky guard with a scarred brow"
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[payload])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        assert cards[0].short_descriptor == "a stocky guard with a scarred brow"

    @allure.story("Short descriptor")
    @allure.title("NPCGenerator truncates the short_descriptor to 80 characters when the LLM overshoots")
    @pytest.mark.asyncio
    async def test_short_descriptor_truncated(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        payload = _full_npc_payload("Aulus")
        payload.short_descriptor = "a " * 60
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[payload])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        assert len(cards[0].short_descriptor) == 80

    @allure.story("Short descriptor")
    @allure.title("NPCGenerator tolerates an empty short_descriptor from the LLM")
    @pytest.mark.asyncio
    async def test_short_descriptor_empty_preserved(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        payload = _full_npc_payload("Aulus")
        payload.short_descriptor = ""
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[payload])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        assert cards[0].short_descriptor == ""


@allure.epic("NPC Interaction")
@allure.feature("NPC Generator")
class TestNameUniquenessAcrossStory:
    @allure.story("Duplicate prevention")
    @allure.title("NPCGenerator forbids names of NPCs met in other scenes, not only the current one")
    @pytest.mark.asyncio
    async def test_names_from_other_scenes_are_forbidden(self, game_state) -> None:
        elsewhere = NPCCard(name="Eira", occupation="net-mender")
        game_state.npcs[elsewhere.uuid] = elsewhere
        game_state.current_scene = Scene(location_id=make_uuid("npc-gen-path"), description="a path")
        gen = NPCGenerator(llm_client=MagicMock())
        send_json = AsyncMock(side_effect=[_full_npc_payload("Eira")])
        with patch.object(gen, _SEND_JSON, new=send_json):
            cards = await gen.act(["net-mender"], {"game_state": game_state})
        assert "Eira" in send_json.await_args_list[0].args[0]
        assert cards[0].name != "Eira"
