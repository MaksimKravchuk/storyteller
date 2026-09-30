"""Story poster persistence: library playbills and on-demand illustrations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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

    async def save_image(self, session_id: str, image: PosterImage) -> bool:
        """Attach the story's one illustration; False if it already has one."""
        posters = tbl.story_posters
        stmt = (
            update(posters)
            .where(posters.c.session_id == session_id, posters.c.image.is_(None))
            .values(image=image.image_bytes, image_mime=image.mime, image_created_at=func.clock_timestamp())
            .returning(posters.c.session_id)
        )
        saved = await self._session.execute(stmt)
        return saved.first() is not None

    async def painted_since(self, web_player_id: str, since: datetime) -> int:
        """Count illustrations painted for a web player's stories since ``since``."""
        posters = tbl.story_posters
        stmt = (
            select(func.count())
            .select_from(posters.join(tbl.sessions, tbl.sessions.c.id == posters.c.session_id))
            .where(tbl.sessions.c.web_player_id == web_player_id, posters.c.image_created_at >= since)
        )
        return int((await self._session.execute(stmt)).scalar() or 0)

    async def get_image_for_player(self, web_player_id: str, game_id: str) -> PosterImage | None:
        """Return the illustration of a player's own, non-archived story, or None."""
        posters = tbl.story_posters
        sessions = tbl.sessions
        stmt = (
            select(posters.c.image, posters.c.image_mime)
            .join(sessions, sessions.c.id == posters.c.session_id)
            .join(tbl.game_states, tbl.game_states.c.session_id == sessions.c.id)
            .where(
                sessions.c.web_player_id == web_player_id,
                sessions.c.archived_at.is_(None),
                tbl.game_states.c.id == game_id,
                posters.c.image.is_not(None),
            )
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        return PosterImage(image_bytes=bytes(row.image), mime=str(row.image_mime))
