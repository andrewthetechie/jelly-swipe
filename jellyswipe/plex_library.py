"""Plex-backed LibraryMediaProvider (ARC-02 parity with legacy app.py)."""

from __future__ import annotations

import random
from typing import List, Optional

import requests

from .base import LibraryMediaProvider


class PlexLibraryProvider(LibraryMediaProvider):
    def __init__(self, plex_url: str, admin_token: str) -> None:
        self._plex_url = plex_url.rstrip("/")
        self._admin_token = admin_token
        self._plex_server = None
        self._genre_cache: Optional[List[str]] = None

    def reset(self) -> None:
        self._plex_server = None
        self._genre_cache = None

    def _get_server(self):
        if self._plex_server is not None:
            return self._plex_server
        from plexapi.server import PlexServer

        self._plex_server = PlexServer(self._plex_url, self._admin_token)
        return self._plex_server

    def _movies_section(self):
        try:
            plex = self._get_server()
            return plex.library.section("Movies")
        except Exception:
            self.reset()
            plex = self._get_server()
            return plex.library.section("Movies")

    def list_genres(self) -> List[str]:
        if self._genre_cache is not None:
            return self._genre_cache
        try:
            section = self._movies_section()
            genres = sorted({g.title for g in section.listFilterChoices(field="genre")})
            display = ["Sci-Fi" if g == "Science Fiction" else g for g in genres]
            self._genre_cache = display
            return display
        except Exception:
            return []

    def fetch_deck(self, genre_name: Optional[str] = None) -> List[dict]:
        movie_section = self._movies_section()
        do_shuffle = True
        search_genre = "Science Fiction" if genre_name == "Sci-Fi" else genre_name

        if genre_name == "Recently Added":
            movies = movie_section.search(
                libtype="movie", sort="addedAt:desc", maxresults=100
            )
            do_shuffle = False
        elif search_genre and search_genre != "All":
            movies = movie_section.search(
                libtype="movie", genre=search_genre, sort="random", maxresults=100
            )
            if not movies and search_genre != genre_name:
                movies = movie_section.search(
                    libtype="movie", genre=genre_name, sort="random", maxresults=100
                )
        else:
            movies = movie_section.search(libtype="movie", sort="random", maxresults=150)

        movie_list = []
        for m in movies:
            runtime_str = ""
            if m.duration:
                hrs = m.duration // 3600000
                mins = (m.duration % 3600000) // 60000
                runtime_str = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m"
            movie_list.append(
                {
                    "id": str(m.ratingKey),
                    "title": m.title,
                    "summary": m.summary,
                    "thumb": f"/proxy?path={m.thumb}",
                    "rating": m.audienceRating or m.rating,
                    "duration": runtime_str,
                    "year": m.year,
                }
            )
        if do_shuffle:
            random.shuffle(movie_list)
        return movie_list

    def resolve_item_for_tmdb(self, movie_id: str):
        try:
            plex = self._get_server()
            return plex.fetchItem(int(movie_id))
        except Exception:
            self.reset()
            return self._get_server().fetchItem(int(movie_id))

    def server_info(self) -> dict:
        try:
            plex = self._get_server()
            return {
                "machineIdentifier": plex.machineIdentifier,
                "name": plex.friendlyName,
            }
        except Exception:
            self.reset()
            plex = self._get_server()
            return {
                "machineIdentifier": plex.machineIdentifier,
                "name": plex.friendlyName,
            }

    def fetch_library_image(self, path: str) -> tuple[bytes, str]:
        if not path or not path.startswith("/library/metadata/"):
            raise PermissionError("Invalid or disallowed image path")
        if not self._plex_url or not self._admin_token:
            raise RuntimeError("Plex image proxy unavailable: missing server configuration")
        url = f"{self._plex_url}{path}?X-Plex-Token={self._admin_token}"
        res = requests.get(url, stream=True)
        res.raise_for_status()
        content_type = res.headers.get("Content-Type", "application/octet-stream")
        return res.content, content_type
