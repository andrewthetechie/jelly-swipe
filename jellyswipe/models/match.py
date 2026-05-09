"""Match schema model."""

from typing import TYPE_CHECKING

from sqlalchemy import Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jellyswipe.models.base import Base

if TYPE_CHECKING:
    from jellyswipe.models.room import Room


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint(
            "room_code", "movie_id", "user_id", name="uq_matches_room_movie_user"
        ),
        Index("ix_matches_status_user_id", "status", "user_id"),
    )

    room_code: Mapped[str] = mapped_column(Text, nullable=False)
    movie_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    thumb: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    deep_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    __mapper_args__ = {
        "primary_key": [room_code, movie_id, user_id],
    }

    room: Mapped["Room | None"] = relationship(
        "Room",
        primaryjoin="foreign(Match.room_code) == Room.pairing_code",
        back_populates="matches",
    )
