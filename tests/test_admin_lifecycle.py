"""Tests for AdminServer start/stop lifecycle and /healthz endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import allure
import aiohttp
import pytest

from interfaces.admin import AdminServer

_HTTP_OK = 200

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin dashboard"),
]


@allure.story("Server lifecycle")
@allure.title("AdminServer binds and responds to /healthz, then cleans up on stop()")
@pytest.mark.asyncio
async def test_admin_server_start_and_stop_serves_healthz() -> None:
    server = AdminServer(MagicMock(), port=0, token=None)

    await server.start()
    try:
        await _assert_healthz_ok(server)
    finally:
        await server.stop()


async def _assert_healthz_ok(server: AdminServer) -> None:
    assert server._runner is not None
    sockets = server._runner.addresses
    assert sockets, "AdminServer did not bind any socket"
    host, port = sockets[0][:2]

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{host}:{port}/healthz") as resp:
            assert resp.status == _HTTP_OK
            payload = await resp.json()
            assert payload == {"status": "ok"}


@allure.story("Server lifecycle")
@allure.title("AdminServer.stop() on a server that never started is a no-op")
@pytest.mark.asyncio
async def test_admin_server_stop_without_start_is_noop() -> None:
    server = AdminServer(MagicMock(), port=0, token=None)

    # No start() — _runner is still None. stop() should not raise.
    await server.stop()
