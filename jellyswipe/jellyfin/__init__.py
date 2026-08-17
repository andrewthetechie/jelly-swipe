"""Jellyfin integration package — split-by-role HTTP client.

The original ``jellyswipe.jellyfin_library.JellyfinLibraryProvider`` god-object
mixed three roles into one thread-locked global. Per ADR-0001 this package
splits them behind a single async HTTP transport:

- ``client.JellyfinClient`` — async ``httpx`` transport.
- ``vault.JellyfinVault`` — delegate token + delegate user resolution.
- ``library.JellyfinLibrary`` — DeckProvider adapter (deck, genres, items,
  server info, images).
- ``watchlist.JellyfinWatchlistWriter`` — add-to-favorites writer.
"""

from __future__ import annotations

from jellyswipe.jellyfin.client import JellyfinClient
from jellyswipe.jellyfin.library import JellyfinLibrary
from jellyswipe.jellyfin.vault import JellyfinVault
from jellyswipe.jellyfin.watchlist import JellyfinWatchlistWriter

__all__ = [
    "JellyfinClient",
    "JellyfinLibrary",
    "JellyfinVault",
    "JellyfinWatchlistWriter",
]
