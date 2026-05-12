"""TMDB cache schema model."""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from jellyswipe.models.base import Base


class TmdbCache(Base):
    __tablename__ = "tmdb_cache"

    media_id: Mapped[str] = mapped_column(Text, primary_key=True)
    lookup_type: Mapped[str] = mapped_column(Text, primary_key=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[str] = mapped_column(Text, nullable=False)
