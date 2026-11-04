"""Test harness: the admin router mounted on a bare FastAPI app, served in-process."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
from fastapi import FastAPI

from interfaces.admin import router
from interfaces.web import deps


def make_admin_app(cfg: Any = None, factory: Any = None) -> FastAPI:
    """Mount the admin router with config and DB-factory overrides (mocks by default)."""
    app = FastAPI()
    app.include_router(router)
    cfg = cfg or MagicMock()
    factory = factory or MagicMock()
    app.dependency_overrides[deps.get_cfg] = MagicMock(return_value=cfg)
    app.dependency_overrides[deps.get_session_factory] = MagicMock(return_value=factory)
    return app


def admin_client(app: FastAPI) -> httpx.AsyncClient:
    """Async client whose relative URLs resolve under ``/admin``."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test/admin")
