"""Phase-1 invariant: metering is byte-identical to a non-metering baseline.

This file is the load-bearing assertion that
`cast/_reliability_metrics` only *observes* — it never alters the
turn's narration output. The test runs the Narrator twice through the
same mocked LLM (identical fixtures), once with the metering buffer
initialised (recorders may fire) and once with the buffer torn down
(recorders are no-ops), and asserts both produced the same string.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast import _reliability_metrics as reliability_metrics
from cast.narrator import Narrator
from cast.schemas.turn_outputs import TurnOutputs
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.scene import PointOfInterest, Scene, SceneNPC
from models.setting import Setting
from tests._uuid_helpers import make_uuid

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Reliability metering"),
]


_NARRATION_BODY = "Narrated prose for the metering inertia test."
_PLAYER_ACTION_KEY = "player_action"
_GAME_STATE_KEY = "game_state"


def _make_game_state() -> GameState:
    setting = Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="The Roman Empire.",
    )
    kg = KnowledgeGraph()
    gs = GameState(setting=setting, knowledge_graph=kg)
    gs.current_scene = Scene(
        location_id=make_uuid("forum"),
        description="The bustling Roman Forum.",
        npcs_present=[SceneNPC(role="guard", uuid=make_uuid("npc-1"))],
        points_of_interest=[PointOfInterest(names=["fountain"])],
        ambient_description="The air smells of roasted nuts.",
    )
    return gs


def _make_narrator() -> Narrator:
    llm_client = AsyncMock()
    llm_client.send_message = AsyncMock(
        return_value=AsyncMock(
            body=_NARRATION_BODY,
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        ),
    )
    return Narrator(llm_client=llm_client, language="English")


async def _run_once() -> str:
    """Drive one Narrator turn with the standard scene fixture."""
    narrator = _make_narrator()
    gs = _make_game_state()
    return await narrator.act(
        input_data=TurnOutputs(scene=gs.current_scene),
        context={_PLAYER_ACTION_KEY: "look around the forum", _GAME_STATE_KEY: gs},
    )


@allure.story("Metering inertia")
@allure.title("Narrator output is byte-identical with metering buffer initialised vs torn down")
@pytest.mark.asyncio
async def test_narration_byte_identical_with_and_without_metering() -> None:
    reliability_metrics.reliability_counters.set(None)
    without_metering = await _run_once()

    reliability_metrics.reset_counters()
    with_metering = await _run_once()

    assert without_metering == with_metering == _NARRATION_BODY


def _raise_collect_failure(*_args, **_kwargs) -> None:
    """Module-level helper so monkeypatch can substitute Narrator's collect_for_turn."""
    raise RuntimeError("forced visible_entities failure")


@allure.story("Metering inertia")
@allure.title("Narrator output is byte-identical when a fallback site fires under metering")
@pytest.mark.asyncio
async def test_narration_byte_identical_when_fallback_fires(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forces ``cast.visible_entities.collect_for_turn`` to raise so the Narrator's
    ``record_fallback("narrator", "visible_entities")`` site actually trips inside
    one of the two runs. Output must still match the un-metered baseline; if it
    diverges, metering has gained an unintended control-flow effect.
    """
    monkeypatch.setattr("cast.narrator.visible_entities.collect_for_turn", _raise_collect_failure)

    reliability_metrics.reliability_counters.set(None)
    without_metering = await _run_once()

    reliability_metrics.reset_counters()
    with_metering = await _run_once()

    assert without_metering == with_metering == _NARRATION_BODY
    # The second run had counters initialised, so the recorder should have fired.
    assert reliability_metrics.snapshot_counters() == {("narrator", "silent_fallback"): 1}
