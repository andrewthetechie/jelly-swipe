"""Swipe schema model."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jellyswipe.models.base import Base

if TYPE_CHECKING:
    from jellyswipe.models.auth_session import AuthSession
    from jellyswipe.models.room import Room


class Swipe(Base):
    __tablename__ = "swipes"
    __table_args__ = (
        Index("ix_swipes_room_movie_direction", "room_code", "movie_id", "direction"),
        Index("ix_swipes_room_movie_session", "room_code", "movie_id", "session_id"),
    )

    room_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("rooms.pairing_code", ondelete="CASCADE"),
        primary_key=True,
    )
    movie_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("auth_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
    )
    __mapper_args__ = {
        "primary_key": [room_code, movie_id, user_id, direction],
    }

    room: Mapped["Room"] = relationship("Room", back_populates="swipes")
    auth_session: Mapped["AuthSession | None"] = relationship("AuthSession", back_populates="swipes")
