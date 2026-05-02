"""End-to-end regression for the user story that motivated PR #108.

The player enters a scene where the NPC "Tony (watchman)" is present
but has not yet been introduced. The collector's entity list and the
inline-wrapped narrator HTML must both refer to "an armed man", never
to "Tony" or "watchman". After introduction the labels flip to Tony /
the watchman and both wrap to the same NPC id.
"""

from __future__ import annotations

import allure

from cast.visible_entities import collect_for_turn
from cast.schemas.turn_outputs import TurnOutputs
from formatting import markdown_render
from formatting.entity_markup import wrap_entities
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from tests._uuid_helpers import make_uuid

_UUID = make_uuid("npc-tony")


def _make_state() -> GameState:
    setting = Setting(name="Test", time_period="now", region="nowhere", summary="")
    gs = GameState(setting=setting, knowledge_graph=KnowledgeGraph())
    card = NPCCard(name="Tony", occupation="watchman", short_descriptor="an armed man")
    card.uuid = _UUID
    gs.npcs[_UUID] = card
    gs.current_scene = Scene(
        location_id=make_uuid("gate"),
        description="The south gate.",
        npcs_present=[SceneNPC(role="guard", uuid=_UUID)],
    )
    return gs


def _render_turn(gs: GameState, prose_md: str) -> tuple[list, str]:
    """Run the entity collection + inline-span pipeline for one narration."""
    entities = collect_for_turn(TurnOutputs(scene=gs.current_scene), gs)
    html = wrap_entities(markdown_render.to_html(prose_md), entities, "English")
    return entities, html


@allure.epic("Narrator & UI")
@allure.feature("Watchman Tony regression")
class TestWatchmanRegression:
    @allure.story("Unintroduced")
    @allure.title("Before introduction the alias is 'an armed man' and no 'Tony' appears in HTML")
    def test_before_introduction(self):
        gs = _make_state()
        entities, html = _render_turn(gs, "An armed man blocks the door.")
        assert len(entities) == 1
        entity = entities[0]
        assert entity.id == str(_UUID)
        assert entity.names == ["an armed man"]
        assert "Tony" not in html
        assert "watchman" not in html
        assert 'data-id="{0}"'.format(_UUID) in html
        # Surface form is preserved so sentence-initial capitalisation stays.
        assert ">An armed man</span>" in html

    @allure.story("After introduction")
    @allure.title("Once known, both 'Tony' and 'the watchman' wrap to the same NPC id")
    def test_after_introduction(self):
        gs = _make_state()
        gs.player.known_npcs.add(_UUID)
        entities, html = _render_turn(gs, "Tony nods. The watchman steps aside.")
        assert entities[0].names == ["Tony (watchman)", "Tony", "the watchman"]
        assert html.count('data-id="{0}"'.format(_UUID)) == 2
        assert ">Tony</span>" in html
        # The surface form is preserved so the sentence-initial capital
        # stays capitalised in the wrapped span.
        assert ">The watchman</span>" in html
