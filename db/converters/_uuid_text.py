"""Stringify UUID-typed model fields bound for ``Text`` DB columns.

Several FK-like columns (``location_id``, ``parent_location_id``,
``owner_id``) remain ``Text`` rather than native UUID, while the domain
models hold real ``uuid.UUID`` values after the KER-44 migration.
asyncpg rejects raw UUID instances bound to text columns, so converters
must stringify on the way out.
"""

from __future__ import annotations

from uuid import UUID


def uuid_to_text(raw_id: UUID | str | None) -> str | None:
    """Return ``None`` for ``None``; otherwise the string form of *raw_id*."""
    if raw_id is None:
        return None
    return str(raw_id)
