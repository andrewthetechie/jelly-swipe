"""Session instance and event models."""

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jellyswipe.models.base import Base


class SessionInstance(Base):
    """Represents a session instance for event streaming."""

    __tablename__ = "session_instances"

    instance_id: Mapped[str] = mapped_column(Text, primary_key=True)
    pairing_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    closed_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    events: Mapped[list["SessionEvent"]] = relationship(
        "SessionEvent",
        back_populates="session_instance",
        cascade="all, delete-orphan",
    )


class SessionEvent(Base):
    """Represents an event in a session's event stream."""

    __tablename__ = "session_events"

    event_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_instance_id: Mapped[str] = mapped_column(
        Text, ForeignKey("session_instances.instance_id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    session_instance: Mapped["SessionInstance"] = relationship(
        "SessionInstance", back_populates="events"
    )

    __table_args__ = (
        Index(
            "ix_session_events_session_instance_id_event_id",
            "session_instance_id",
            "event_id",
        ),
    )
