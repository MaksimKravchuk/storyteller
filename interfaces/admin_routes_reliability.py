"""Admin reliability dashboard route."""

from __future__ import annotations

from fastapi import Request
from starlette.responses import Response

from db.repo_admin_reliability import VALID_WINDOWS, reliability_aggregates
from interfaces import admin_route_helpers as helpers
from interfaces.admin_json import _json_response

_HTTP_BAD_REQUEST = 400
_DEFAULT_WINDOW = "24h"


async def reliability_summary(request: Request) -> Response:
    """Return aggregated reliability counters grouped by (agent, event_type).

    Query param ``window``: one of ``24h``, ``7d``, ``30d`` (default ``24h``).
    Returns ``{window, rows: [{agent, event_type, total}]}``.
    """
    window = request.query_params.get("window", _DEFAULT_WINDOW)
    if window not in VALID_WINDOWS:
        return _json_response(
            {"error": "window must be one of: {0}".format(", ".join(sorted(VALID_WINDOWS)))},
            status=_HTTP_BAD_REQUEST,
        )
    async with helpers.open_repo(request) as repo:
        rows = await reliability_aggregates(repo.admin.session, window=window)
    return _json_response({"window": window, "rows": rows})
