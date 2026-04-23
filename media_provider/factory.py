"""Process-wide library provider singleton (ARC-01, ARC-03)."""

from __future__ import annotations

import os
from typing import Optional

from media_provider.base import LibraryMediaProvider
from media_provider.plex_library import PlexLibraryProvider

_provider_singleton: Optional[LibraryMediaProvider] = None


def _normalized_media_provider() -> str:
    raw = (os.getenv("MEDIA_PROVIDER") or "").strip().lower()
    if not raw:
        return "plex"
    if raw not in ("plex", "jellyfin"):
        raise RuntimeError(
            f"Invalid MEDIA_PROVIDER={os.getenv('MEDIA_PROVIDER')!r}; use 'plex' or 'jellyfin'"
        )
    return raw


def get_provider() -> LibraryMediaProvider:
    global _provider_singleton

    if _normalized_media_provider() != "plex":
        raise RuntimeError(
            "Plex library access is unavailable when MEDIA_PROVIDER=jellyfin "
            "(not implemented until later phases)."
        )

    if _provider_singleton is None:
        plex_url = os.getenv("PLEX_URL", "").rstrip("/")
        admin_token = os.getenv("PLEX_TOKEN")
        _provider_singleton = PlexLibraryProvider(plex_url, admin_token)
    return _provider_singleton


def reset() -> None:
    global _provider_singleton
    if _provider_singleton is not None:
        _provider_singleton.reset()
    _provider_singleton = None
