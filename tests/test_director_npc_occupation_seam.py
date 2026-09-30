"""Consumer-seam test: NPC occupations reach the Director's rendered system prompt."""

from __future__ import annotations

import allure

from cast.director_context import ContextFormatter
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from prompts.director_prompts import DIRECTOR_SYSTEM
from tests._uuid_helpers import make_uuid


class _CapturingPerformer:
    """Minimal stub that records ``set_context`` kwargs for rendering."""

    def __init__(self) -> None:
        self.kwargs: dict[str, str] = {}

    def set_context(self, **kwargs: str) -> None:
        self.kwargs.update(kwargs)


@allure.epic("NPC Interaction")
@allure.feature("Director context formatting")
@allure.story("NPC label formatting")
@allure.title("The Director's rendered system prompt names each present NPC's occupation")
def test_director_system_prompt_carries_npc_occupation() -> None:
    npc = NPCCard(name="Marcus", occupation="forum guard", physical_status="healthy")
    setting = Setting(name="Rome", time_period="1 AD", region="Italy", summary="")
    gs = GameState(setting=setting, knowledge_graph=KnowledgeGraph())
    gs.npcs[npc.uuid] = npc
    gs.current_scene = Scene(
        location_id=make_uuid("forum"),
        description="A quiet Roman forum.",
        npcs_present=[SceneNPC(role="forum guard", uuid=npc.uuid)],
    )
    performer = _CapturingPerformer()

    ContextFormatter(gs).sync_context(performer)
    rendered = DIRECTOR_SYSTEM.render(language="English", **performer.kwargs)

    assert "NPCs present:\n- Marcus, forum guard" in rendered
