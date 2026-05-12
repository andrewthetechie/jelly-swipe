"""Session instance and event repositories."""

from __future__ import annotations

from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncConnection as AsyncConnection

from jellyswipe.models.session_event import SessionEvent, SessionInstance


def append_sync(
    conn: Connection,
    instance_id: str,
    event_type: str,
    payload_json: str,
) -> int:
    """Append a session event using a sync Connection (for use inside run_sync).

    Returns the auto-generated event_id.
    """
    from datetime import datetime, timezone

    created_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        text("""
            INSERT INTO session_events (session_instance_id, event_type, payload_json, created_at)
            VALUES (:instance_id, :event_type, :payload_json, :created_at)
        """),
        {
            "instance_id": instance_id,
            "event_type": event_type,
            "payload_json": payload_json,
            "created_at": created_at,
        },
    )
    result = conn.execute(text("SELECT last_insert_rowid()"))
    return result.scalar()


class SessionInstanceRepository:
    """Repository for session instance persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, instance_id: str, pairing_code: str) -> None:
        """Create a new session instance."""
        from datetime import datetime, timezone

        self._session.add(
            SessionInstance(
                instance_id=instance_id,
                pairing_code=pairing_code,
                status="active",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    async def get_by_pairing_code(self, code: str) -> SessionInstance | None:
        """Get a session instance by pairing code."""
        result = await self._session.execute(
            select(SessionInstance).where(SessionInstance.pairing_code == code)
        )
        return result.scalar_one_or_none()

    async def get_by_instance_id(self, instance_id: str) -> SessionInstance | None:
        """Get a session instance by instance ID."""
        result = await self._session.execute(
            select(SessionInstance).where(SessionInstance.instance_id == instance_id)
        )
        return result.scalar_one_or_none()

    async def mark_closing(self, instance_id: str) -> None:
        """Mark a session instance as closing."""
        from datetime import datetime, timezone

        instance = await self.get_by_instance_id(instance_id)
        if instance:
            instance.status = "closing"
            instance.closed_at = datetime.now(timezone.utc).isoformat()
            await self._session.flush()

    async def mark_closed(self, instance_id: str) -> None:
        """Mark a session instance as closed."""
        await self._session.execute(
            text("""
                UPDATE session_instances
                SET status = :status
                WHERE instance_id = :instance_id
            """),
            {"status": "closed", "instance_id": instance_id},
        )
        await self._session.flush()

    async def delete(self, instance_id: str) -> None:
        """Delete a session instance."""
        await self._session.execute(
            delete(SessionInstance).where(SessionInstance.instance_id == instance_id)
        )

    async def is_pairing_code_reserved(self, code: str) -> bool:
        """Check if a pairing code is reserved (active or closing)."""
        result = await self._session.execute(
            select(func.count()).where(
                SessionInstance.pairing_code == code,
                SessionInstance.status.in_(["active", "closing"]),
            )
        )
        count = result.scalar()
        return (count or 0) > 0

    async def cleanup_closed_before(self, cutoff_iso: str) -> int:
        """Delete closed instances created before the cutoff."""
        result = await self._session.execute(
            text("""
                DELETE FROM session_instances
                WHERE status = 'closed' AND created_at < :cutoff
            """),
            {"cutoff": cutoff_iso},
        )
        return result.rowcount or 0

    async def get_closing_before(self, cutoff_iso: str) -> list[SessionInstance]:
        """Get instances marked as 'closing' before the cutoff time."""
        result = await self._session.execute(
            text("""
                SELECT * FROM session_instances
                WHERE status = 'closing' AND closed_at < :cutoff
            """),
            {"cutoff": cutoff_iso},
        )
        rows = result.mappings().all()
        instances = []
        for row in rows:
            instances.append(
                SessionInstance(
                    instance_id=row["instance_id"],
                    pairing_code=row["pairing_code"],
                    status=row["status"],
                    created_at=row["created_at"],
                    closed_at=row["closed_at"],
                )
            )
        return instances


class SessionEventRepository:
    """Repository for session event persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, instance_id: str, event_type: str, payload_json: str) -> int:
        """Append an event and return the new event_id."""
        from datetime import datetime, timezone

        event = SessionEvent(
            session_instance_id=instance_id,
            event_type=event_type,
            payload_json=payload_json,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._session.add(event)
        await self._session.flush()
        return event.event_id

    async def read_after(
        self, instance_id: str, after_event_id: int, limit: int = 100
    ) -> list[SessionEvent]:
        """Read events after a given event_id for an instance."""
        result = await self._session.execute(
            select(SessionEvent)
            .where(
                SessionEvent.session_instance_id == instance_id,
                SessionEvent.event_id > after_event_id,
            )
            .order_by(SessionEvent.event_id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def read_latest_event_id(self, instance_id: str) -> int | None:
        """Get the latest event_id for an instance."""
        result = await self._session.execute(
            select(func.max(SessionEvent.event_id)).where(
                SessionEvent.session_instance_id == instance_id
            )
        )
        return result.scalar()

    async def delete_for_instance(self, instance_id: str) -> int:
        """Delete all events for an instance."""
        result = await self._session.execute(
            delete(SessionEvent).where(SessionEvent.session_instance_id == instance_id)
        )
        return result.rowcount or 0

    async def append_raw_sql(
        self,
        conn: AsyncConnection,
        instance_id: str,
        event_type: str,
        payload_json: str,
    ) -> int:
        """Append an event using raw SQL connection."""
        from datetime import datetime, timezone

        created_at = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            text("""
                INSERT INTO session_events (session_instance_id, event_type, payload_json, created_at)
                VALUES (:instance_id, :event_type, :payload_json, :created_at)
            """),
            {
                "instance_id": instance_id,
                "event_type": event_type,
                "payload_json": payload_json,
                "created_at": created_at,
            },
        )
        # Get the last inserted rowid
        result = await conn.execute(text("SELECT last_insert_rowid()"))
        return result.scalar()
