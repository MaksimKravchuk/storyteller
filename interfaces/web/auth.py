"""Supabase Auth helpers and beta invite gate dependencies."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any, Mapping

import jwt as pyjwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from config import Config
from interfaces.web.auth_models import AuthenticatedUser, SupabaseClaims
from defaults.entitlements import normalize_user_plan
from interfaces.web.errors import guard_account_query

_AUTH_PREFIX = "Bearer "
_AUTH_REQUIRED_DETAIL = "Authentication required"
_AUTH_MALFORMED_DETAIL = "Malformed Authorization header"
_AUTH_INVALID_DETAIL = "Invalid authentication token"
_INVITE_REQUIRED_DETAIL = "Invite required"
_EMAIL_REQUIRED_DETAIL = "Authenticated user email is required"
_MISSING_JWKS_DETAIL = "Supabase JWKS URL is not configured"
_JWKS_CACHE_LIFESPAN_SECONDS = 300
_JWKS_FETCH_TIMEOUT_SECONDS = 5.0


def is_auth_required(cfg: Config) -> bool:
    """Return True only when the explicit beta auth flag is enabled."""
    return cfg.beta_auth_required is True


async def verify_supabase_token(token: str, cfg: Config) -> SupabaseClaims:
    """Verify a Supabase JWT and return the claims needed by the beta gate."""
    if not cfg.supabase_jwks_url:
        raise ValueError(_MISSING_JWKS_DETAIL)
    payload = await asyncio.to_thread(_decode_supabase_payload, token, cfg)
    sub = str(payload.get("sub") or "")
    email = str(payload.get("email") or "")
    if not sub or not email:
        raise ValueError("Supabase token is missing sub or email")
    return SupabaseClaims(sub=sub, email=email)


async def get_current_user(request: Request, cfg: Config, repo: Any) -> AuthenticatedUser:
    """Authenticate the request and enforce the beta invite gate."""
    token = _bearer_token(request)
    try:
        claims = await verify_supabase_token(token, cfg)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_AUTH_INVALID_DETAIL) from exc
    if not claims.email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_EMAIL_REQUIRED_DETAIL)
    if cfg.beta_invite_gate_enabled is not False:
        invited = await guard_account_query(repo.accounts.is_email_invited, claims.email)
        if not invited:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_INVITE_REQUIRED_DETAIL)
    account = await guard_account_query(repo.accounts.get_or_create_for_invited_user, claims.sub, claims.email)
    return _authenticated_user(account, claims)


def _decode_supabase_payload(token: str, cfg: Config) -> Mapping[str, Any]:
    client = _get_supabase_jwks_client(str(cfg.supabase_jwks_url))
    signing_key = client.get_signing_key_from_jwt(token)
    return pyjwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience=cfg.supabase_jwt_audience or None,
        issuer=cfg.supabase_jwt_issuer,
        options={"verify_aud": bool(cfg.supabase_jwt_audience)},
    )


@lru_cache(maxsize=8)
def _get_supabase_jwks_client(jwks_url: str) -> PyJWKClient:
    """Return a process-lifetime cached JWKS client with bounded network fetches."""
    return PyJWKClient(
        jwks_url,
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=_JWKS_CACHE_LIFESPAN_SECONDS,
        timeout=_JWKS_FETCH_TIMEOUT_SECONDS,
    )


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization")
    if not header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_AUTH_REQUIRED_DETAIL)
    if not header.startswith(_AUTH_PREFIX):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_AUTH_MALFORMED_DETAIL)
    token = header[len(_AUTH_PREFIX) :].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_AUTH_MALFORMED_DETAIL)
    return token


def _authenticated_user(account: Mapping[str, Any], claims: SupabaseClaims) -> AuthenticatedUser:
    return AuthenticatedUser(
        account_id=str(account["id"]),
        supabase_user_id=str(account.get("supabase_user_id") or claims.sub),
        email=str(account.get("email") or claims.email).strip().lower(),
        plan=normalize_user_plan(account.get("plan")),
        is_admin=bool(account.get("is_admin")),
        mature_content=bool(account.get("mature_content")),
    )
