"""Library media provider abstraction (ARC-01).

Routes and higher-level features depend on this contract for all
Plex/Jellyfin-backed library I/O. Phase 2 implements Plex only; Jellyfin
arrives in later phases.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional, Tuple


class LibraryMediaProvider(abc.ABC):
    """Abstract library backend: genres, deck, TMDB chain, server id, images."""

    @abc.abstractmethod
    def reset(self) -> None:
        """Invalidate cached connections (mirrors legacy reset_plex)."""

    @abc.abstractmethod
    def list_genres(self) -> List[str]:
        """Genre labels for UI (includes Sci-Fi vs Science Fiction normalization)."""

    @abc.abstractmethod
    def fetch_deck(self, genre_name: Optional[str] = None) -> List[dict]:
        """Movie cards: id, title, summary, thumb, rating, duration, year."""

    @abc.abstractmethod
    def resolve_item_for_tmdb(self, movie_id: str) -> Any:
        """Plex library item for TMDB search (title/year); implements retry+reset."""

    @abc.abstractmethod
    def server_info(self) -> dict:
        """Return dict with machineIdentifier and name (friendly)."""

    @abc.abstractmethod
    def fetch_library_image(self, path: str) -> Tuple[bytes, str]:
        """
        Validated upstream image bytes and Content-Type.

        Raises PermissionError if path is missing or does not start with
        /library/metadata/ (maps to HTTP 403). Raises on missing server config
        so routes can return 503.
        """
