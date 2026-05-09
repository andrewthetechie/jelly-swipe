"""Library media provider abstraction (ARC-01).

Routes and higher-level features depend on this contract for all
Jellyfin-backed library I/O. Implements Jellyfin media provider.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional, Tuple


class LibraryMediaProvider(abc.ABC):
    """Abstract library backend: genres, deck, TMDB chain, server id, images."""

    @abc.abstractmethod
    def reset(self) -> None:
        """Invalidate cached connections (mirrors legacy reset behavior)."""

    @abc.abstractmethod
    def list_genres(self) -> List[str]:
        """Genre labels for UI (includes Sci-Fi vs Science Fiction normalization)."""

    @abc.abstractmethod
    def fetch_deck(
        self,
        media_types: List[str],
        genre_name: Optional[str] = None,
        hide_watched: bool = False,
    ) -> List[dict]:
        """Media cards: id, title, summary, thumb, rating, duration, year, media_type."""

    @abc.abstractmethod
    def resolve_item_for_tmdb(self, movie_id: str) -> Any:
        """Media library item for TMDB search (title/year); implements retry+reset."""

    @abc.abstractmethod
    def server_info(self) -> dict:
        """Return dict with machineIdentifier and name (friendly)."""

    @abc.abstractmethod
    def fetch_library_image(self, path: str) -> Tuple[bytes, str]:
        """
        Validated upstream image bytes and Content-Type.

        Path must match ``jellyfin/{id}/Primary`` where id is a 32-char hex
        or 36-char UUID string. Raises PermissionError for invalid paths
        (HTTP 403). Raises on missing server config so routes can return 503.
        """
