"""Story poster persistence: library playbills and on-demand illustrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl


@dataclass(frozen=True)
class PosterImage:
    """A stored poster illustration."""

    image_bytes: bytes
    mime: str


class PosterStore:
    """Async operations on ``story_posters`` (one row per session)."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._session = db_session

    async def save_playbill(self, session_id: str, playbill: dict[str, Any]) -> None:
        """Insert or replace the playbill for a session, keeping any illustration."""
        stmt = insert(tbl.story_posters).values(session_id=session_id, playbill=playbill)
        stmt = stmt.on_conflict_do_update(
            index_elements=[tbl.story_posters.c.session_id],
            set_={"playbill": stmt.excluded.playbill},
        )
        await self._session.execute(stmt)

    async def get_playbill(self, session_id: str) -> tuple[dict[str, Any], bool] | None:
        """Return ``(playbill, has_image)`` without loading image bytes, or None."""
        posters = tbl.story_posters
        has_image = posters.c.image.is_not(None).label("has_image")
        is_session = posters.c.session_id == session_id
        stmt = select(posters.c.playbill, has_image).where(is_session)
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        return dict(row.playbill), bool(row.has_image)

    async def save_image(self, session_id: str, image: PosterImage) -> None:
        """Attach an illustration to an existing playbill row."""
        stmt = (
            update(tbl.story_posters)
            .where(tbl.story_posters.c.session_id == session_id)
            .values(image=image.image_bytes, image_mime=image.mime, image_created_at=func.clock_timestamp())
        )
        await self._session.execute(stmt)

    async def get_image(self, session_id: str) -> PosterImage | None:
        """Return the stored illustration for a session, or None."""
        posters = tbl.story_posters
        stmt = select(posters.c.image, posters.c.image_mime).where(
            posters.c.session_id == session_id,
            posters.c.image.is_not(None),
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        return PosterImage(image_bytes=bytes(row.image), mime=str(row.image_mime))
