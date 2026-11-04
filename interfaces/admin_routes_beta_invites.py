"""Admin beta invite route handlers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import re

from fastapi import Request
from starlette.responses import Response

from db.repo_beta_invites import BetaInviteStore
from interfaces import admin_route_helpers as helpers
from interfaces.admin_json import _json_response

_HTTP_BAD_REQUEST = 400
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def list_beta_invites(request: Request) -> Response:
    """Return beta invite rows for admin management."""
    async with _open_store(request) as store:
        invites = await store.list_invites()
    return _json_response({"invites": invites})


async def create_beta_invite(request: Request) -> Response:
    """Create or re-enable a beta invite from the admin dashboard."""
    email = _submitted_email(await _json_payload(request))
    if email is None:
        return _json_response({"error": "Valid email is required"}, status=_HTTP_BAD_REQUEST)
    async with helpers.open_session(request) as db_session:
        invite = await BetaInviteStore(db_session).upsert_invite(email)
        await db_session.commit()
    return _json_response({"invite": invite})


@asynccontextmanager
async def _open_store(request: Request) -> AsyncIterator[BetaInviteStore]:
    async with helpers.open_session(request) as db_session:
        yield BetaInviteStore(db_session)


async def _json_payload(request: Request) -> object:
    try:
        return await request.json()
    except ValueError:
        return {}


def _submitted_email(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw_email = payload.get("email")
    if not isinstance(raw_email, str):
        return None
    email = raw_email.strip().lower()
    if not _EMAIL_RE.fullmatch(email):
        return None
    return email
