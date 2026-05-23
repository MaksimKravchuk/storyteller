"""Tests for AdminServer start/stop lifecycle, /healthz endpoint, and auth middleware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import allure
import pytest
from aiohttp import ClientSession, web
from interfaces.admin import AdminServer

_HTTP_OK = 200
_HTTP_UNAUTHORIZED = 401

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin dashboard"),
]


@allure.story("Server lifecycle")
@allure.title("AdminServer binds and responds to /healthz, then cleans up on stop()")
@pytest.mark.asyncio
async def test_admin_server_start_and_stop_serves_healthz() -> None:
    server = AdminServer(MagicMock(), MagicMock(), port=0, token=None)

    await server.start()
    try:
        await _assert_healthz_ok(server)
    finally:
        await server.stop()


async def _assert_healthz_ok(server: AdminServer) -> None:
    assert server.bound_address is not None, "AdminServer did not bind any socket"
    host, port = server.bound_address

    async with ClientSession() as session:
        async with session.get(f"http://{host}:{port}/healthz") as resp:
            assert resp.status == _HTTP_OK
            payload = await resp.json()
            assert payload == {"status": "ok"}


@allure.story("Server lifecycle")
@allure.title("AdminServer.stop() on a server that never started is a no-op and leaves it unbound")
@pytest.mark.asyncio
async def test_admin_server_stop_without_start_is_noop() -> None:
    server = AdminServer(MagicMock(), MagicMock(), port=0, token=None)

    # No start() — _runner is still None. stop() should not raise.
    await server.stop()

    # And the invariant: an unstarted server reports no bound address.
    assert server.bound_address is None


async def _empty_sessions(_request: web.Request) -> web.Response:
    return web.json_response({"sessions": []})


@allure.story("Server lifecycle")
@allure.title("AdminServer auth middleware rejects unauthorized /api/* and accepts with Bearer token")
@pytest.mark.asyncio
async def test_admin_server_auth_middleware_rejects_and_accepts() -> None:
    with patch("interfaces.admin_routes.list_sessions", _empty_sessions):
        server = AdminServer(MagicMock(), MagicMock(), port=0, token="secret")

    await server.start()
    try:
        await _assert_auth_middleware_behavior(server)
    finally:
        await server.stop()


async def _assert_auth_middleware_behavior(server: AdminServer) -> None:
    assert server.bound_address is not None
    host, port = server.bound_address
    base = f"http://{host}:{port}"

    async with ClientSession() as session:
        # No Authorization header → middleware returns 401.
        async with session.get(f"{base}/api/sessions") as resp:
            assert resp.status == _HTTP_UNAUTHORIZED

        # Correct bearer token → middleware lets the request through.
        headers = {"Authorization": "Bearer secret"}
        async with session.get(f"{base}/api/sessions", headers=headers) as resp:
            assert resp.status == _HTTP_OK
            payload = await resp.json()
            assert payload == {"sessions": []}

        # /healthz is outside /api/* and must never be gated.
        async with session.get(f"{base}/healthz") as resp:
            assert resp.status == _HTTP_OK
