"""Tests for the library playbill: builder, start-game seam, and library rows."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from interfaces.web import playbill, service
from interfaces.web.library_rows import game_summary_from_row
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]

_STORY = "Story posters"
_TAGLINE_LIMIT = 161  # 160 chars of text plus the ellipsis
_OPENING = "Morning *fog* clings to the columns of the **Forum** as you step out. A merchant waves."


def _staged_state(game_state: GameState) -> GameState:
    """Put the player in a district with one introduced NPC and one stranger present."""
    forum = Location(name="Forum Romanum", location_type="district")
    game_state.locations[forum.uuid] = forum
    game_state.player.location_id = forum.uuid
    game_state.player.name = "Gaius"
    game_state.player.appearance = "a lean scribe with inky fingers"
    marcus = NPCCard(name="Marcus", occupation="merchant", short_descriptor="a nervous merchant")
    lucia = NPCCard(name="Lucia", occupation="augur", short_descriptor="a hooded augur")
    game_state.npcs[marcus.uuid] = marcus
    game_state.npcs[lucia.uuid] = lucia
    game_state.player.known_npcs.add(marcus.uuid)
    game_state.current_scene = Scene(
        location_id=forum.uuid,
        npcs_present=[SceneNPC(role="trader", uuid=marcus.uuid), SceneNPC(role="seer", uuid=lucia.uuid)],
    )
    game_state.conversation_log = [{"player_action": "", "response": _OPENING}]
    return game_state


@allure.story(_STORY)
@allure.title("tagline_from_opening keeps the first sentence as plain text")
def test_tagline_is_first_sentence_without_markdown() -> None:
    assert playbill.tagline_from_opening(_OPENING) == "Morning fog clings to the columns of the Forum as you step out."


@allure.story(_STORY)
@allure.title("tagline_from_opening clips a long first sentence at a word boundary")
def test_tagline_clips_long_sentence() -> None:
    tagline = playbill.tagline_from_opening("word " * 60)

    assert tagline.endswith("word…")
    assert len(tagline) <= _TAGLINE_LIMIT


@allure.story(_STORY)
@allure.title("tagline_from_opening returns an empty tagline when there is no opening")
def test_tagline_empty_opening() -> None:
    assert not playbill.tagline_from_opening("")


@allure.story(_STORY)
@allure.title("build_playbill projects hero, era, place and time from the post-prologue state")
def test_build_playbill_projects_state(game_state: GameState) -> None:
    bill = playbill.build_playbill(_staged_state(game_state))

    assert bill.hero == "Gaius"
    assert bill.hero_look == "a lean scribe with inky fingers"
    assert (bill.era, bill.region) == ("1st century AD", "Italy")
    assert (bill.place, bill.place_type) == ("Forum Romanum", "district")
    assert bill.daypart == game_state.game_time
    assert bill.tagline.startswith("Morning fog")


@allure.story(_STORY)
@allure.title("build_playbill bills strangers by descriptor, never by an unlearned name")
def test_build_playbill_cast_is_name_gated(game_state: GameState) -> None:
    bill = playbill.build_playbill(_staged_state(game_state))

    assert [(member.label, member.known) for member in bill.cast] == [
        ("Marcus (merchant)", True),
        ("a hooded augur", False),
    ]
    assert "Lucia" not in bill.model_dump_json()


@allure.story(_STORY)
@allure.title("build_playbill bills at most four cast members")
def test_build_playbill_caps_cast(game_state: GameState) -> None:
    staged = _staged_state(game_state)
    assert staged.current_scene is not None
    staged.current_scene.npcs_present = [SceneNPC(role="extra {0}".format(index), uuid=None) for index in range(6)]

    assert len(playbill.build_playbill(staged).cast) == 4


@allure.story(_STORY)
@allure.title("build_playbill falls back to a generic place when the player has no location")
def test_build_playbill_without_location(game_state: GameState) -> None:
    bill = playbill.build_playbill(game_state)

    assert (bill.place, bill.place_type) == (None, "generic")


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("save_playbill stores the built playbill for the session")
async def test_save_playbill_writes_poster_row(game_state: GameState) -> None:
    repo = MagicMock()
    repo.web_games.posters.save_playbill = AsyncMock()

    save = repo.web_games.posters.save_playbill
    await playbill.save_playbill(repo, "sess-1", _staged_state(game_state))

    session_id, stored = save.await_args.args
    assert session_id == "sess-1"
    assert stored["hero"] == "Gaius"
    assert stored["cast"][1] == {"label": "a hooded augur", "known": False}


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("save_playbill never blocks a game start when the playbill cannot be built")
async def test_save_playbill_skips_unbuildable_state() -> None:
    repo = MagicMock()
    repo.web_games.posters.save_playbill = AsyncMock()

    with patch.object(playbill, "build_playbill", side_effect=ValueError("boom")):
        await playbill.save_playbill(repo, "sess-1", MagicMock())

    repo.web_games.posters.save_playbill.assert_not_awaited()


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("start_game_for_player stores the new story's playbill before committing")
async def test_start_game_saves_playbill_before_commit(game_state: GameState) -> None:
    staged = _staged_state(game_state)
    calls: list[str] = []
    repo = AsyncMock()
    repo.sessions = MagicMock()
    repo.sessions.create_web = AsyncMock(return_value={"id": "sess-1", "language": "English"})
    repo.sessions.update = AsyncMock()
    repo.web_games.posters.save_playbill = AsyncMock(side_effect=lambda *_: calls.append("playbill"))
    repo.commit = AsyncMock(side_effect=lambda: calls.append("commit"))
    engine = MagicMock()
    engine.start_game = AsyncMock()
    engine.assert_running = MagicMock(return_value=(staged, MagicMock(), MagicMock(all_events=[])))
    start_request = service.StartGameParams(player_id="player-1", setting="Rome", language="English")

    with (
        patch("engine.session_ops.create_engine", return_value=engine),
        patch("engine.session_ops.load_role_overrides", new=AsyncMock(return_value={})),
    ):
        await service.start_game_for_player(repo=repo, cfg=MagicMock(), start_request=start_request)

    save = repo.web_games.posters.save_playbill
    session_id, stored = save.await_args.args
    assert session_id == "sess-1"
    assert stored["place"] == "Forum Romanum"
    assert calls == ["playbill", "commit"]


@allure.story(_STORY)
@allure.title("game_summary_from_row carries a stored playbill and illustration flag to the card")
def test_summary_row_carries_playbill(game_state: GameState) -> None:
    stored = playbill.build_playbill(_staged_state(game_state)).model_dump()
    row = {
        "game_id": "g1",
        "title": "Ides",
        "setting": "Rome",
        "turn_count": 3,
        "playbill": stored,
        "has_poster_image": True,
    }

    summary = game_summary_from_row(row)

    assert summary.playbill is not None
    assert summary.playbill.hero == "Gaius"
    assert summary.has_poster_image is True


@allure.story(_STORY)
@allure.title("game_summary_from_row shows the plain card for a missing or unreadable playbill")
def test_summary_row_tolerates_bad_playbill() -> None:
    base = {"game_id": "g1", "title": "Ides", "setting": "Rome", "turn_count": 3}

    assert game_summary_from_row(base).playbill is None
    assert game_summary_from_row({**base, "playbill": {"tagline": "only"}}).playbill is None
    assert game_summary_from_row(base).has_poster_image is False
