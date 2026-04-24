"""Admin-settings store — operator-mutable key-value overrides.

Currently used only for per-role model overrides. Kept outside
``repo_admin`` because that module is read-only; writes live here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from defaults.models import PROVIDER_ANTHROPIC, PROVIDER_OPENAI, PROVIDER_OPENROUTER

ALLOWED_ROLES: frozenset[str] = frozenset(("director", "agent", "narrator", "dramaturge"))
ALLOWED_PROVIDERS: frozenset[str] = frozenset(
    (PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OPENROUTER),
)

_MODEL_KEY_PREFIX = "model."

_MODEL_ID_MAX_LENGTH = 200


def _model_key(role: str) -> str:
    return "{0}{1}".format(_MODEL_KEY_PREFIX, role)


def _role_from_key(stored_key: str) -> str:
    return stored_key[len(_MODEL_KEY_PREFIX) :]


def _row_to_override(row: Any) -> tuple[str, tuple[str, str]]:
    return _role_from_key(row["key"]), (row["provider"], row["model_id"])


def _validate_role(role: str) -> None:
    if role not in ALLOWED_ROLES:
        raise ValueError("unknown role: {0}".format(role))


def _validate_provider(provider: str) -> None:
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError("unknown provider: {0}".format(provider))


def _validate_model_id(model_id: str) -> None:
    if not model_id or len(model_id) > _MODEL_ID_MAX_LENGTH:
        raise ValueError("model_id must be 1..{0} chars".format(_MODEL_ID_MAX_LENGTH))


class AdminSettingsStore:
    """Async CRUD for ``admin_settings``."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._session = db_session

    async def get_model_overrides(self) -> dict[str, tuple[str, str]]:
        """Return ``{role: (provider, model_id)}`` for every stored override."""
        role_keys = tuple(_model_key(role) for role in ALLOWED_ROLES)
        stmt = select(
            tbl.admin_settings.c.key,
            tbl.admin_settings.c.provider,
            tbl.admin_settings.c.model_id,
        ).where(tbl.admin_settings.c.key.in_(role_keys))
        query_result = await self._session.execute(stmt)
        return dict(_row_to_override(row) for row in query_result.mappings().all())

    async def set_model(self, role: str, provider: str, model_id: str) -> None:
        """Upsert a role → (provider, model_id) override."""
        _validate_role(role)
        _validate_provider(provider)
        _validate_model_id(model_id)
        payload = {
            "key": _model_key(role),
            "provider": provider,
            "model_id": model_id,
        }
        stmt = pg_insert(tbl.admin_settings).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={"provider": provider, "model_id": model_id, "updated_at": func.now()},
        )
        await self._session.execute(stmt)
