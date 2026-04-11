"""Coverage for interfaces.admin_routes_detail — all 6 detail endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_admin import _make_app

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin detail routes"),
]

_HTTP_OK = 200
_SESSION_ID = "sess-xyz"
_BASE = "/api/sessions/{0}".format(_SESSION_ID)


def _prime_get_db(mock_get_db) -> None:
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)


async def _do_request(mock_repo, url: str) -> tuple[int, object]:
    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get(url)
            status = resp.status
            body = await resp.json()
    return status, body


@allure.story("Knowledge")
@allure.title("/knowledge detail route returns the graph payload from repo.admin.get_knowledge_graph")
@pytest.mark.asyncio
async def test_knowledge_route_returns_graph_payload() -> None:
    """knowledge returns the dict produced by repo.admin.get_knowledge_graph."""
    payload = {"nodes": [{"id": "n1"}], "edges": [{"from": "n1", "to": "n2"}]}
    mock_repo = AsyncMock()
    mock_repo.admin.get_knowledge_graph.return_value = payload

    status, body = await _do_request(mock_repo, "{0}/knowledge".format(_BASE))

    assert status == _HTTP_OK
    assert body == payload
    mock_repo.admin.get_knowledge_graph.assert_awaited_once_with(_SESSION_ID)


@allure.story("Events")
@allure.title("/events detail route wraps fetch_events output in an {'events': [...]} envelope")
@pytest.mark.asyncio
async def test_events_route_wraps_fetch_events() -> None:
    """events returns {'events': <list>} from fetch_events."""
    events_list = [{"id": "e1", "description": "thunderstorm"}]
    mock_repo = AsyncMock()

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
            patch(
                "interfaces.admin_routes_detail.fetch_events",
                new=AsyncMock(return_value=events_list),
            ) as fetch_mock,
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("{0}/events".format(_BASE))
            status = resp.status
            body = await resp.json()
            fetch_mock.assert_awaited_once()

    assert status == _HTTP_OK
    assert body == {"events": events_list}


@allure.story("NPCs")
@allure.title("/npcs detail route wraps repo.admin.get_npcs output in an {'npcs': [...]} envelope")
@pytest.mark.asyncio
async def test_npcs_route_returns_npc_list() -> None:
    """npcs returns the list produced by repo.admin.get_npcs."""
    npc_rows = [{"name": "Marcus"}, {"name": "Julia"}]
    mock_repo = AsyncMock()
    mock_repo.admin.get_npcs.return_value = npc_rows

    status, body = await _do_request(mock_repo, "{0}/npcs".format(_BASE))

    assert status == _HTTP_OK
    assert body == {"npcs": npc_rows}
    mock_repo.admin.get_npcs.assert_awaited_once_with(_SESSION_ID)


@allure.story("Locations")
@allure.title("/locations detail route wraps repo.admin.get_locations in a {'locations': [...]} envelope")
@pytest.mark.asyncio
async def test_locations_route_returns_location_list() -> None:
    """locations returns the list produced by repo.admin.get_locations."""
    loc_rows = [{"name": "Forum"}]
    mock_repo = AsyncMock()
    mock_repo.admin.get_locations.return_value = loc_rows

    status, body = await _do_request(mock_repo, "{0}/locations".format(_BASE))

    assert status == _HTTP_OK
    assert body == {"locations": loc_rows}
    mock_repo.admin.get_locations.assert_awaited_once_with(_SESSION_ID)


@allure.story("Scenes")
@allure.title("/scenes detail route wraps fetch_scenes output in a {'scenes': [...]} envelope")
@pytest.mark.asyncio
async def test_scenes_route_wraps_fetch_scenes() -> None:
    """scenes returns {'scenes': <list>} from fetch_scenes."""
    scene_rows = [{"id": "s1"}, {"id": "s2"}]
    mock_repo = AsyncMock()

    async with TestClient(TestServer(_make_app())) as client:
        with (
            patch("interfaces.admin_route_helpers.get_db") as mock_get_db,
            patch("interfaces.admin_route_helpers.GameRepository", return_value=mock_repo),
            patch(
                "interfaces.admin_routes_detail.fetch_scenes",
                new=AsyncMock(return_value=scene_rows),
            ) as fetch_mock,
        ):
            _prime_get_db(mock_get_db)
            resp = await client.get("{0}/scenes".format(_BASE))
            status = resp.status
            body = await resp.json()
            fetch_mock.assert_awaited_once()

    assert status == _HTTP_OK
    assert body == {"scenes": scene_rows}


@allure.story("AI calls")
@allure.title("/ai-calls without a turn query passes turn_number=None to ai_logs.get")
@pytest.mark.asyncio
async def test_ai_calls_no_turn_passes_none() -> None:
    """Without ?turn, ai_logs.get is called with turn_number=None."""
    logs = [{"id": "log-1"}]
    mock_repo = AsyncMock()
    mock_repo.ai_logs.get.return_value = logs

    status, body = await _do_request(mock_repo, "{0}/ai-calls".format(_BASE))

    assert status == _HTTP_OK
    assert body == {"ai_calls": logs}
    mock_repo.ai_logs.get.assert_awaited_once_with(_SESSION_ID, turn_number=None)


@allure.story("AI calls")
@allure.title("/ai-calls?turn=3 parses the turn query param and forwards turn_number=3 to ai_logs.get")
@pytest.mark.asyncio
async def test_ai_calls_with_turn_passes_int() -> None:
    """With ?turn=3, ai_logs.get is called with turn_number=3."""
    logs = [{"id": "log-turn-3"}]
    mock_repo = AsyncMock()
    mock_repo.ai_logs.get.return_value = logs

    status, body = await _do_request(mock_repo, "{0}/ai-calls?turn=3".format(_BASE))

    assert status == _HTTP_OK
    assert body == {"ai_calls": logs}
    mock_repo.ai_logs.get.assert_awaited_once_with(_SESSION_ID, turn_number=3)
