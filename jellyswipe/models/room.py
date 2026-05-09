"""Room schema model."""

from typing import TYPE_CHECKING

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from jellyswipe.models.base import Base

if TYPE_CHECKING:
    from jellyswipe.models.match import Match
    from jellyswipe.models.swipe import Swipe


class Room(Base):
    __tablename__ = "rooms"

    pairing_code: Mapped[str] = mapped_column(Text, primary_key=True)
    movie_data: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    ready: Mapped[int] = mapped_column(nullable=False, server_default="0")
    current_genre: Mapped[str] = mapped_column(Text, nullable=False, server_default="All")
    solo_mode: Mapped[int] = mapped_column(nullable=False, server_default="0")
    last_match_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    deck_position: Mapped[str | None] = mapped_column(Text, nullable=True)
    deck_order: Mapped[str | None] = mapped_column(Text, nullable=True)
    include_movies: Mapped[int] = mapped_column(nullable=False, server_default="1")
    include_tv_shows: Mapped[int] = mapped_column(nullable=False, server_default="0")
    hide_watched: Mapped[int] = mapped_column(nullable=False, server_default="0")

    swipes: Mapped[list["Swipe"]] = relationship(
        "Swipe",
        back_populates="room",
        cascade="all, delete-orphan",
    )
    matches: Mapped[list["Match"]] = relationship(
        "Match",
        primaryjoin="foreign(Match.room_code) == Room.pairing_code",
        back_populates="room",
    )
