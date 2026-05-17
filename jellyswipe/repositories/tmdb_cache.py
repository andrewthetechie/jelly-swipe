"""Async TMDB cache persistence."""

from __future__ import annotations

from dataclasses import dataclass

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from jellyswipe.models.tmdb_cache import TmdbCache


@dataclass(slots=True)
class TmdbCacheRecord:
    media_id: str
    lookup_type: str
    result_json: str
    fetched_at: str


class TmdbCacheRepository:
    """Persistence access for TMDB cache entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self, media_id: str, lookup_type: str, max_age_days: int = 7
    ) -> TmdbCacheRecord | None:
        """Return cached result if fresh (within max_age_days), else None."""
        stmt = select(TmdbCache).where(
            TmdbCache.media_id == media_id,
            TmdbCache.lookup_type == lookup_type,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        fetched = datetime.fromisoformat(row.fetched_at)
        if fetched <= cutoff:
            return None

        return TmdbCacheRecord(
            media_id=row.media_id,
            lookup_type=row.lookup_type,
            result_json=row.result_json,
            fetched_at=row.fetched_at,
        )

    async def put(self, media_id: str, lookup_type: str, result_json: str) -> None:
        """Upsert cache entry with current timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        await self._session.execute(
            text(
                "INSERT INTO tmdb_cache (media_id, lookup_type, result_json, fetched_at) "
                "VALUES (:media_id, :lookup_type, :result_json, :fetched_at) "
                "ON CONFLICT(media_id, lookup_type) DO UPDATE SET "
                "result_json = :result_json, fetched_at = :fetched_at"
            ),
            {
                "media_id": media_id,
                "lookup_type": lookup_type,
                "result_json": result_json,
                "fetched_at": now,
            },
        )

    async def cleanup_stale(self, max_age_days: int = 30) -> int:
        """Delete entries older than max_age_days. Returns count deleted."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        result = await self._session.execute(
            text("DELETE FROM tmdb_cache WHERE fetched_at < :cutoff"),
            {"cutoff": cutoff},
        )
        return result.rowcount or 0
