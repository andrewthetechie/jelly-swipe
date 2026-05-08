"""Auth session schema model."""

from typing import TYPE_CHECKING

from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jellyswipe.models.base import Base

if TYPE_CHECKING:
    from jellyswipe.models.swipe import Swipe


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_created_at", "created_at"),
    )

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    jellyfin_token: Mapped[str] = mapped_column(Text, nullable=False)
    jellyfin_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    swipes: Mapped[list["Swipe"]] = relationship("Swipe", back_populates="auth_session")
