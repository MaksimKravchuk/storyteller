"""JSON response helper for the admin API."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from starlette.responses import Response


def _json_serial(unknown: Any) -> Any:
    """JSON serializer for objects not handled by default json."""
    if isinstance(unknown, (date, datetime)):
        return unknown.isoformat()
    if isinstance(unknown, UUID):
        return str(unknown)
    raise TypeError(f"Type {type(unknown)} not serializable")


def _json_response(payload: Any, status: int = 200) -> Response:
    return Response(
        content=json.dumps(payload, default=_json_serial),
        media_type="application/json",
        status_code=status,
    )
