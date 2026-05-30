"""Operator-managed search-provider settings — helpers for ``AdminSettingsStore``.

The search provider selection and its credentials are persisted in the same
generic ``admin_settings`` key/value table as the model overrides, under the
``search.`` key prefix (no migration): the value lives in the ``model_id``
column and the ``provider`` column carries a namespace sentinel to satisfy its
NOT NULL constraint. Unlike model API keys (which stay in env), the operator
chose to keep the Tavily key / SearXNG URL here so they are fully manageable —
including deletion — from the admin dashboard.

These are free functions taking an :class:`AsyncSession` so the public CRUD can
live as three thin methods on :class:`db.repo_settings.AdminSettingsStore`
without overflowing its method budget.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from research.search_factory import PROVIDER_SEARXNG, PROVIDER_TAVILY, PROVIDER_WIKIPEDIA

_COL_KEY = "key"
_COL_PROVIDER = "provider"
_COL_VALUE = "model_id"

ALLOWED_SEARCH_PROVIDERS: frozenset[str] = frozenset(
    (PROVIDER_WIKIPEDIA, PROVIDER_TAVILY, PROVIDER_SEARXNG),
)
SEARCH_FIELDS: frozenset[str] = frozenset((_COL_PROVIDER, "tavily_api_key", "searxng_base_url"))

_SEARCH_KEY_PREFIX = "search."
_SEARCH_NAMESPACE = "search"
_SEARCH_VALUE_MAX_LENGTH = 500


def _search_key(name: str) -> str:
    return "{0}{1}".format(_SEARCH_KEY_PREFIX, name)


def _name_from_key(stored_key: str) -> str:
    return stored_key[len(_SEARCH_KEY_PREFIX) :]


def _validate_field(name: str, setting_value: str) -> None:
    if name not in SEARCH_FIELDS:
        raise ValueError("unknown search field: {0}".format(name))
    if name == _COL_PROVIDER and setting_value not in ALLOWED_SEARCH_PROVIDERS:
        raise ValueError("unknown search provider: {0}".format(setting_value))
    if not setting_value or len(setting_value) > _SEARCH_VALUE_MAX_LENGTH:
        raise ValueError("search value must be 1..{0} chars".format(_SEARCH_VALUE_MAX_LENGTH))


def _key_in_search():
    """SQL predicate matching every stored ``search.*`` key."""
    keys = [_search_key(name) for name in SEARCH_FIELDS]
    return tbl.admin_settings.c.key.in_(keys)


async def read_search(session: AsyncSession) -> dict[str, str]:
    """Return ``{name: value}`` for every stored ``search.*`` setting."""
    stmt = select(tbl.admin_settings.c.key, tbl.admin_settings.c.model_id)
    stmt = stmt.where(_key_in_search())
    result = await session.execute(stmt)
    mapping: dict[str, str] = {}
    for row in result.mappings().all():
        mapping[_name_from_key(row[_COL_KEY])] = row[_COL_VALUE]
    return mapping


async def write_search(session: AsyncSession, name: str, setting_value: str) -> None:
    """Upsert one search setting (``provider`` / ``tavily_api_key`` / ``searxng_base_url``)."""
    _validate_field(name, setting_value)
    payload = {_COL_KEY: _search_key(name), _COL_PROVIDER: _SEARCH_NAMESPACE, _COL_VALUE: setting_value}
    stmt = pg_insert(tbl.admin_settings).values(**payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=[_COL_KEY],
        set_={_COL_PROVIDER: _SEARCH_NAMESPACE, _COL_VALUE: setting_value, "updated_at": func.now()},
    )
    await session.execute(stmt)


async def delete_search(session: AsyncSession) -> None:
    """Delete every stored ``search.*`` setting, reverting to env/defaults."""
    stmt = delete(tbl.admin_settings).where(_key_in_search())
    await session.execute(stmt)
