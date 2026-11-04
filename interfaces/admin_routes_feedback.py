"""Admin routes for beta feedback review and export."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from fastapi import Request
from starlette.responses import Response

from interfaces import admin_route_helpers as helpers
from interfaces.admin_json import _json_response

_DEFAULT_LIMIT = 500
_CSV_FIELDS = (
    "created_at",
    "user_id",
    "user_email",
    "game_id",
    "session_id",
    "turn_number",
    "category",
    "setting",
    "message",
)
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _limit(request: Request) -> int:
    raw_limit = request.query_params.get("limit")
    if raw_limit is None:
        return _DEFAULT_LIMIT
    return int(raw_limit)


def _stringify(raw_value: Any) -> str:
    if raw_value is None:
        return ""
    return str(raw_value)


def _csv_cell(raw_value: Any) -> str:
    """Return a CSV-safe cell value for spreadsheet review."""
    text = _stringify(raw_value)
    return _quote_formula_cell(text) if text.lstrip().startswith(_CSV_FORMULA_PREFIXES) else text


def _quote_formula_cell(text: str) -> str:
    """Neutralise spreadsheet formulas in user-controlled CSV cells."""
    return f"'{text}"


async def list_feedback(request: Request) -> Response:
    """Return recent beta feedback for admin review."""
    async with helpers.open_repo(request) as repo:
        rows = await repo.feedback.list_recent(limit=_limit(request))
    return _json_response({"feedback": rows})


async def export_feedback_csv(request: Request) -> Response:
    """Export recent beta feedback as CSV for offline review."""
    async with helpers.open_repo(request) as repo:
        rows = await repo.feedback.list_recent(limit=_limit(request))
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_cell(row.get(field)) for field in _CSV_FIELDS})
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=storyteller-beta-feedback.csv"},
    )
