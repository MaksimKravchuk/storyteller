"""Unit tests for the ``autonomy_three_guards_tavern`` scenario state builder.

Keeps the cheap structural invariants (pre-seeded NPCs, scene roster,
location roster) under guard without going through the paid-LLM
benchmark harness.
"""

from __future__ import annotations

import allure

from benchmarks.scenarios.autonomy_three_guards_tavern.state import build_state

_GUARD_NAMES = frozenset(("Aulus", "Bassus", "Cato"))


@allure.epic("Benchmarks")
@allure.feature("autonomy_three_guards_tavern state")
class TestAutonomyStateSeedsGuards:
    @allure.story("Pre-seeded roster")
    @allure.title("build_state registers all three guards in game_state.npcs by stable UUID")
    def test_guards_in_game_state_npcs(self) -> None:
        scenario_state = build_state()
        names = {npc.name for npc in scenario_state.game_state.npcs.values()}
        assert _GUARD_NAMES <= names

    @allure.story("Pre-seeded roster")
    @allure.title("build_state puts each guard on the starting scene's npcs_present with its seeded UUID")
    def test_guards_in_scene_npcs_present(self) -> None:
        scenario_state = build_state()
        scene = scenario_state.game_state.current_scene
        assert scene is not None
        scene_uuids = {snpc.uuid for snpc in scene.npcs_present if snpc.uuid}
        npcs = scenario_state.game_state.npcs
        scene_names = {npcs[uid].name for uid in scene_uuids if uid in npcs}
        assert _GUARD_NAMES <= scene_names

    @allure.story("Pre-seeded roster")
    @allure.title("build_state registers each guard on the location's npcs_present (KER-33)")
    def test_guards_in_location_npcs_present(self) -> None:
        """Mirrors ``Director._register_new_npc``'s ``location.add_npc`` call
        for LLM-generated NPCs so proximity-witness and occupancy queries
        see the pre-seeded guards without waiting for a scene rebuild.
        """
        scenario_state = build_state()
        gs = scenario_state.game_state
        assert gs.player.location_id is not None
        location = gs.locations[gs.player.location_id]
        roster_uuids = {uuid for uuid, npc in gs.npcs.items() if npc.name in _GUARD_NAMES}
        assert roster_uuids <= set(location.npcs_present)

    @allure.story("Consistency")
    @allure.title("Scene time_of_day matches game_time so the staleness check sees a fresh scene")
    def test_scene_time_matches_game_time(self) -> None:
        scenario_state = build_state()
        gs = scenario_state.game_state
        assert gs.current_scene is not None
        assert gs.current_scene.time_of_day == gs.game_time
