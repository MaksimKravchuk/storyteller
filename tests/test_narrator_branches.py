"""Tests for Narrator input-branch coverage (items, wait, npc_turns, completed events)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.narrator import Narrator
from cast.schemas.turn_outputs import DialogueEntry, NPCTurnEntry, TurnOutputs
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from models.world_state import WorldState


def _make_narrator() -> Narrator:
    llm_client = AsyncMock()
    llm_client.send_message = AsyncMock(
        return_value=AsyncMock(
            body="Narrated text.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
    )
    return Narrator(llm_client=llm_client, language="English")


def _make_game_state() -> GameState:
    setting = Setting(name="Rome", time_period="1 AD", region="Italy", summary="")
    gs = GameState(setting=setting, knowledge_graph=KnowledgeGraph())
    return gs


def _last_user_body(narrator: Narrator) -> str:
    call = narrator.llm_client.send_message.call_args  # type: ignore[attr-defined]
    return call.kwargs["messages"][-1].body


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorInputBranches:
    @allure.story("Item examination")
    @allure.title("Narrator prompt includes item examination lines under 'Item examined:'")
    @pytest.mark.asyncio
    async def test_item_examination_rendered(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(item_examination=["A bronze amulet engraved with runes."]),
            context={"player_action": "inspect amulet", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "Item examined: A bronze amulet engraved with runes." in body

    @allure.story("Wait action")
    @allure.title("Narrator describes a voluntary wait as the player observing the surroundings")
    @pytest.mark.asyncio
    async def test_wait_voluntary_default(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(wait=True),
            context={"player_action": "wait", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "waits and observes" in body

    @allure.story("Wait action")
    @allure.title("Narrator describes a voluntary-labelled wait the same way as a bare wait flag")
    @pytest.mark.asyncio
    async def test_wait_voluntary_explicit(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(wait=True, wait_reason="voluntary"),
            context={"player_action": "wait", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "waits and observes" in body

    @allure.story("Wait action")
    @allure.title("Narrator surfaces the wait reason when the player is incapacitated and cannot act")
    @pytest.mark.asyncio
    async def test_wait_involuntary_surfaces_reason(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(wait=True, wait_reason="unconscious"),
            context={"player_action": "attack", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "cannot act" in body
        assert "unconscious" in body

    @allure.story("NPC turns")
    @allure.title("Narrator prompt surfaces simultaneous NPC turns under a 'Meanwhile' heading")
    @pytest.mark.asyncio
    async def test_npc_turns_rendered(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(
                npc_turns=[
                    NPCTurnEntry(npc_name="Guard", action="draws his sword", action_type="COMBAT"),
                    NPCTurnEntry(npc_name="Merchant", action="ducks behind a barrel", action_type="IDLE"),
                ],
            ),
            context={"player_action": "shout", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "Meanwhile, Guard: draws his sword" in body
        assert "Meanwhile, Merchant: ducks behind a barrel" in body

    @allure.story("Completed events")
    @allure.title("Narrator forwards completed_events into the prompt as a bulleted list")
    @pytest.mark.asyncio
    async def test_completed_events_forwarded(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(completed_events=["The storm passes.", "A messenger arrives."]),
            context={"player_action": "wait for news", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "The storm passes." in body
        assert "A messenger arrives." in body


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorSceneFallback:
    @allure.story("Scene rendering")
    @allure.title("Narrator renders the scene description verbatim under a 'Scene:' heading")
    @pytest.mark.asyncio
    async def test_scene_description_rendered(self):
        narrator = _make_narrator()
        gs = _make_game_state()
        scene = Scene(location_id="anywhere", description="A plain string scene descriptor.")

        await narrator.act(
            input_data=TurnOutputs(scene=scene),
            context={"player_action": "look", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "Scene: A plain string scene descriptor." in body


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorNpcDepartures:
    @allure.story("NPC departures")
    @allure.title("Narrator silently skips npc_departures when the list is empty (dormant path)")
    @pytest.mark.asyncio
    async def test_empty_departures_is_no_op(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(),
            context={"player_action": "look", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "Someone departs" not in body

    @allure.story("NPC departures")
    @allure.title("Narrator renders npc_departures lines under a 'Someone departs:' prefix")
    @pytest.mark.asyncio
    async def test_populated_departures_rendered(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(
                npc_departures=[
                    "Marco (bartender) heads off to his quarters for the night",
                    "Lia (baker) leaves for the market",
                ],
            ),
            context={"player_action": "wait", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "Someone departs: Marco (bartender) heads off to his quarters for the night" in body
        assert "Someone departs: Lia (baker) leaves for the market" in body


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorWorldMood:
    @allure.story("World mood")
    @allure.title("Narrator system prompt omits the world_mood section when world_state.world_mood is None")
    @pytest.mark.asyncio
    async def test_world_mood_unset_skips_section(self):
        narrator = _make_narrator()
        gs = _make_game_state()
        assert gs.world_state.world_mood is None

        await narrator.act(
            input_data=TurnOutputs(),
            context={"player_action": "look", "game_state": gs},
        )

        call_args = narrator.llm_client.send_message.call_args
        system_prompt = call_args.kwargs["system_prompt"]
        assert "Current world mood" not in system_prompt

    @allure.story("World mood")
    @allure.title("Narrator system prompt includes world_mood on NEW_SCENE turns when world_state.world_mood is set")
    @pytest.mark.asyncio
    async def test_world_mood_rendered_on_new_scene(self):
        narrator = _make_narrator()
        gs = _make_game_state()
        gs.world_state = WorldState(world_mood="tense and restless")
        scene = Scene(location_id="forum", description="The Forum.")

        await narrator.act(
            input_data=TurnOutputs(scene=scene),
            context={"player_action": "enter forum", "game_state": gs},
        )

        call_args = narrator.llm_client.send_message.call_args
        system_prompt = call_args.kwargs["system_prompt"]
        assert "Current world mood: tense and restless" in system_prompt

    @allure.story("World mood")
    @allure.title("Narrator system prompt omits world_mood on CONTINUATION turns to avoid per-action embroidery")
    @pytest.mark.asyncio
    async def test_world_mood_omitted_on_continuation(self):
        """Weaving mood into every small action produces cliché padding."""
        narrator = _make_narrator()
        gs = _make_game_state()
        gs.world_state = WorldState(world_mood="tense and restless")

        await narrator.act(
            input_data=TurnOutputs(),
            context={"player_action": "look", "game_state": gs},
        )

        call_args = narrator.llm_client.send_message.call_args
        system_prompt = call_args.kwargs["system_prompt"]
        assert "Current world mood" not in system_prompt


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestFormatNpcLabel:
    @allure.story("NPC label formatting")
    @allure.title("Narrator labels introduced NPCs (uuid in known_npcs) as 'Name (Occupation)'")
    @pytest.mark.asyncio
    async def test_known_npc_uses_name_and_occupation(self):
        narrator = _make_narrator()
        gs = _make_game_state()
        npc = NPCCard(name="Marcus", occupation="centurion", short_descriptor="a tall man in a red cloak")
        gs.npcs[npc.uuid] = npc
        gs.player.known_npcs.add(npc.uuid)

        scene = Scene(
            location_id="forum",
            description="The Forum.",
            npcs_present=[SceneNPC(role="soldier", uuid=npc.uuid)],
        )

        await narrator.act(
            input_data=TurnOutputs(scene=scene),
            context={"player_action": "enter", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "Marcus (centurion)" in body
        assert "a tall man in a red cloak" not in body

    @allure.story("NPC label formatting")
    @allure.title("Narrator renders introduced NPC aliases as 'Name (Occupation) (aka: Name, the occupation)'")
    @pytest.mark.asyncio
    async def test_known_npc_emits_aka_synonyms(self):
        narrator = _make_narrator()
        gs = _make_game_state()
        npc = NPCCard(name="Marcus", occupation="centurion")
        gs.npcs[npc.uuid] = npc
        gs.player.known_npcs.add(npc.uuid)

        scene = Scene(
            location_id="forum",
            description="The Forum.",
            npcs_present=[SceneNPC(role="soldier", uuid=npc.uuid)],
        )

        await narrator.act(
            input_data=TurnOutputs(scene=scene),
            context={"player_action": "enter", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "Marcus (centurion) (aka: Marcus, the centurion)" in body

    @allure.story("NPC label formatting")
    @allure.title("Narrator omits the '(aka: …)' suffix for unknown NPCs that only have a single descriptor")
    @pytest.mark.asyncio
    async def test_unknown_npc_has_no_aka_suffix(self):
        narrator = _make_narrator()
        gs = _make_game_state()
        npc = NPCCard(name="Marcus", occupation="centurion", short_descriptor="a tall man in a red cloak")
        gs.npcs[npc.uuid] = npc

        scene = Scene(
            location_id="forum",
            description="The Forum.",
            npcs_present=[SceneNPC(role="soldier", uuid=npc.uuid)],
        )

        await narrator.act(
            input_data=TurnOutputs(scene=scene),
            context={"player_action": "enter", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "a tall man in a red cloak" in body
        assert "(aka:" not in body

    @allure.story("NPC label formatting")
    @allure.title("Narrator hides the name of NPCs not yet in known_npcs and uses short_descriptor instead")
    @pytest.mark.asyncio
    async def test_unknown_npc_with_descriptor_hides_name(self):
        narrator = _make_narrator()
        gs = _make_game_state()
        npc = NPCCard(name="Marcus", occupation="centurion", short_descriptor="a tall man in a red cloak")
        gs.npcs[npc.uuid] = npc

        scene = Scene(
            location_id="forum",
            description="The Forum.",
            npcs_present=[SceneNPC(role="soldier", uuid=npc.uuid)],
        )

        await narrator.act(
            input_data=TurnOutputs(scene=scene),
            context={"player_action": "enter", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "a tall man in a red cloak" in body
        assert "Marcus" not in body
        assert "centurion" not in body

    @allure.story("NPC label formatting")
    @allure.title("Narrator falls back to SceneNPC.role when the card has no short_descriptor and is not known")
    @pytest.mark.asyncio
    async def test_unknown_npc_without_descriptor_falls_back_to_role(self):
        narrator = _make_narrator()
        gs = _make_game_state()
        npc = NPCCard(name="Marcus", occupation="centurion")
        gs.npcs[npc.uuid] = npc

        scene = Scene(
            location_id="forum",
            description="The Forum.",
            npcs_present=[SceneNPC(role="soldier", uuid=npc.uuid)],
        )

        await narrator.act(
            input_data=TurnOutputs(scene=scene),
            context={"player_action": "enter", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "soldier" in body
        assert "Marcus" not in body

    @allure.story("NPC label formatting")
    @allure.title("Narrator falls back to SceneNPC.role and warns when a scene uuid is missing from game_state.npcs")
    @pytest.mark.asyncio
    async def test_orphaned_scene_uuid_falls_back_and_warns(self, loguru_sink):
        narrator = _make_narrator()
        gs = _make_game_state()

        scene = Scene(
            location_id="forum",
            description="The Forum.",
            npcs_present=[SceneNPC(role="soldier", uuid="evicted-uuid")],
        )

        await narrator.act(
            input_data=TurnOutputs(scene=scene),
            context={"player_action": "enter", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert "soldier" in body
        warning_messages = [rec["message"] for rec in loguru_sink if rec["level"].name == "WARNING"]
        assert any("evicted-uuid" in msg for msg in warning_messages)


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorDedup:
    """Two Director paths can emit dialogue for the same NPC on one turn
    (primary response + retaliation summary), and the same is possible
    for npc_turns. The Narrator must collapse these per-NPC so the
    rendered prose doesn't serialise them into an 'and then… and then…'
    cadence.
    """

    @allure.story("Dedup")
    @allure.title("Exact-duplicate dialogue entries collapse to a single 'Name says:' bullet")
    @pytest.mark.asyncio
    async def test_exact_duplicate_dialogue_collapses(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(
                dialogue=[
                    DialogueEntry(npc_name="Ivan", response="Halt!"),
                    DialogueEntry(npc_name="Ivan", response="Halt!"),
                ],
            ),
            context={"player_action": "approach", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert body.count("Ivan says: Halt!") == 1

    @allure.story("Dedup")
    @allure.title("Multiple distinct dialogue entries for one NPC merge into a single bullet")
    @pytest.mark.asyncio
    async def test_same_npc_distinct_responses_merge(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(
                dialogue=[
                    DialogueEntry(npc_name="Ivan", response="Halt!"),
                    DialogueEntry(npc_name="Ivan", response="Who goes there?"),
                ],
            ),
            context={"player_action": "approach", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert body.count("Ivan says:") == 1
        assert "Ivan says: Halt! / Who goes there?" in body

    @allure.story("Dedup")
    @allure.title("Duplicate NPC-turn actions collapse to a single 'Meanwhile' bullet")
    @pytest.mark.asyncio
    async def test_duplicate_npc_turn_actions_collapse(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(
                npc_turns=[
                    NPCTurnEntry(npc_name="Frol", action="draws his sword", action_type="COMBAT"),
                    NPCTurnEntry(npc_name="Frol", action="draws his sword", action_type="COMBAT"),
                ],
            ),
            context={"player_action": "shout", "game_state": gs},
        )

        body = _last_user_body(narrator)
        assert body.count("Meanwhile, Frol:") == 1
