"""Admin cost telemetry endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aiohttp import web

from costs.reports import build_cost_summary
from interfaces import admin_route_helpers

_HTTP_BAD_REQUEST = 400


def _parse_datetime(raw_datetime: str | None) -> datetime | None:
    """Parse optional ISO datetime query params."""
    if not raw_datetime:
        return None
    return datetime.fromisoformat(raw_datetime.replace("Z", "+00:00"))


def _parse_period(request: web.Request) -> tuple[datetime | None, datetime | None]:
    """Parse optional ISO datetime filter params."""
    start_at = _parse_datetime(request.query.get("start_at"))
    end_at = _parse_datetime(request.query.get("end_at"))
    return start_at, end_at


async def _cost_summary_payload(request: web.Request) -> dict[str, Any]:
    """Fetch usage rows and return cost summary payload."""
    cfg = admin_route_helpers.get_cfg(request)
    try:
        start_at, end_at = _parse_period(request)
    except ValueError as exc:
        raise web.HTTPBadRequest(reason="Invalid ISO datetime query parameter") from exc
    async with admin_route_helpers.open_repo(request) as repo:
        rows = await repo.ai_logs.usage_summary(start_at=start_at, end_at=end_at)
    return build_cost_summary(rows, cfg)


async def beta_cost_summary(request: web.Request) -> web.Response:
    """Return prompt-free beta LLM usage and cost summary JSON."""
    try:
        payload = await _cost_summary_payload(request)
    except web.HTTPBadRequest:
        return admin_route_helpers._json_response(
            {"error": "Invalid ISO datetime query parameter"},
            status=_HTTP_BAD_REQUEST,
        )
    payload["currency"] = "USD"
    payload["date_basis"] = "UTC"
    return admin_route_helpers._json_response(payload)
