"""Jellyfin library reader — DeckProvider adapter.

Implements the ``DeckProvider`` protocol (``fetch_deck``) plus the catalog
reads that media/trailer/cast/genres/server-info/image routes need. All
methods are async and perform no blocking I/O on the event loop: HTTP goes
through the shared async :class:`~jellyswipe.jellyfin.client.JellyfinClient`
with authentication delegated to :class:`~jellyswipe.jellyfin.vault.JellyfinVault`.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from jellyswipe.jellyfin_media_item import (
    display_genre_name,
    movie_to_media_item,
    query_genre_name,
    series_to_media_item,
)

if TYPE_CHECKING:
    from jellyswipe.jellyfin.vault import JellyfinVault

logger = logging.getLogger(__name__)


# Allowlisted proxy path: jellyfin/{item_id}/Primary
# Accept both canonical UUID and 32-char hex ids returned by Jellyfin.
_JF_IMAGE_PATH = re.compile(r"^jellyfin/([0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$")


class JellyfinLibrary:
    """Jellyfin-backed library: genres, deck, images, item resolution, server info."""

    def __init__(self, vault: JellyfinVault) -> None:
        self._vault = vault
        self._cached_library_ids: dict[str, list[str]] = {}
        self._genre_cache: dict[str, list[str]] = {}

    async def _library_ids_for_type(self, collection_type: str) -> list[str]:
        """Return all library IDs matching the given collection type."""
        if collection_type in self._cached_library_ids:
            return self._cached_library_ids[collection_type]

        uid = await self._vault.delegate_user_id()
        data = await self._vault.api("GET", f"/Users/{uid}/Views")
        ids: list[str] = []
        for v in data.get("Items") or []:
            ct = (v.get("CollectionType") or "").lower()
            if ct == collection_type.lower():
                lid = v.get("Id")
                if lid:
                    ids.append(lid)

        self._cached_library_ids[collection_type] = ids
        return ids

    async def _movies_library_id(self) -> str:
        """Legacy method for backward compatibility — returns first movies library."""
        ids = await self._library_ids_for_type("movies")
        if not ids:
            raise RuntimeError(
                "Jellyfin: no library with CollectionType=movies — add a Movies library on the server."
            )
        return ids[0]

    async def list_genres(self) -> list[str]:
        cache_key = "all"
        if cache_key in self._genre_cache:
            return self._genre_cache[cache_key]

        uid = await self._vault.delegate_user_id()
        names: list[str] = []

        # Query genres from movie libraries
        movie_libs = await self._library_ids_for_type("movies")
        for lib in movie_libs:
            data = await self._vault.api(
                "GET",
                "/Items/Filters",
                params={
                    "ParentId": lib,
                    "UserId": uid,
                    "IncludeItemTypes": "Movie",
                },
            )
            for g in data.get("GenreFilters") or data.get("Genres") or []:
                if isinstance(g, dict):
                    n = g.get("Name") or g.get("Value")
                else:
                    n = str(g)
                if n:
                    names.append(n)

        # Query genres from TV libraries
        tv_libs = await self._library_ids_for_type("tvshows")
        for lib in tv_libs:
            data = await self._vault.api(
                "GET",
                "/Items/Filters",
                params={
                    "ParentId": lib,
                    "UserId": uid,
                    "IncludeItemTypes": "Series",
                },
            )
            for g in data.get("GenreFilters") or data.get("Genres") or []:
                if isinstance(g, dict):
                    n = g.get("Name") or g.get("Value")
                else:
                    n = str(g)
                if n:
                    names.append(n)

        if not names:
            # Fallback to /Genres endpoint for movie libraries
            for lib in movie_libs:
                try:
                    gdata = await self._vault.api(
                        "GET",
                        "/Genres",
                        params={"ParentId": lib, "UserId": uid},
                    )
                    for it in gdata.get("Items") or []:
                        n = it.get("Name")
                        if n:
                            names.append(n)
                except RuntimeError:
                    pass

        names = sorted({n for n in names if n})
        display = [display_genre_name(n) for n in names]
        self._genre_cache[cache_key] = display
        return display

    async def fetch_deck(
        self,
        media_types: list[str],
        genre_name: str | None = None,
        hide_watched: bool = False,
    ) -> list[dict]:
        """Fetch deck cards for the specified media types.

        Args:
            media_types: List of media types to fetch ("movie", "tv_show").
            genre_name: Optional genre filter.
            hide_watched: When True, filter out watched items via Jellyfin's Filters=IsNotPlayed.

        Returns:
            List of card dicts with media_type field set.
        """
        uid = await self._vault.delegate_user_id()
        all_items: list[dict] = []

        # Fetch movies
        if "movie" in media_types:
            movie_libs = await self._library_ids_for_type("movies")
            for lib in movie_libs:
                items = await self._fetch_items_for_library(
                    lib=lib,
                    uid=uid,
                    item_type="Movie",
                    genre_name=genre_name,
                    hide_watched=hide_watched,
                )
                all_items.extend(items)

        # Fetch TV shows
        if "tv_show" in media_types:
            tv_libs = await self._library_ids_for_type("tvshows")
            for lib in tv_libs:
                items = await self._fetch_items_for_library(
                    lib=lib,
                    uid=uid,
                    item_type="Series",
                    genre_name=genre_name,
                    hide_watched=hide_watched,
                )
                all_items.extend(items)

        # Transform items to cards
        cards: list[dict] = []
        for it in all_items:
            item_type = it.get("Type", "")
            if item_type == "Series":
                cards.append(series_to_media_item(it))
            else:
                cards.append(movie_to_media_item(it))

        # Shuffle if not recently added
        search_genre = query_genre_name(genre_name)
        if search_genre not in ("Recently Added", None, "All"):
            random.shuffle(cards)

        return cards

    async def _fetch_items_for_library(
        self,
        lib: str,
        uid: str,
        item_type: str,
        genre_name: str | None,
        hide_watched: bool = False,
    ) -> list[dict]:
        """Fetch items from a single library."""
        params: dict[str, Any] = {
            "ParentId": lib,
            "UserId": uid,
            "IncludeItemTypes": item_type,
            "Recursive": "true",
            "Fields": "Overview,RunTimeTicks,ProductionYear,CommunityRating,CriticRating,ChildCount",
        }

        # Add Filters=IsNotPlayed when hide_watched is True
        if hide_watched:
            params["Filters"] = "IsNotPlayed"

        search_genre = query_genre_name(genre_name)

        if genre_name == "Recently Added":
            params["Limit"] = 100
            params["SortBy"] = "DateCreated"
            params["SortOrder"] = "Descending"
        elif search_genre and search_genre != "All":
            params["Limit"] = 100
            params["Genres"] = search_genre
            params["SortBy"] = "Random"
        else:
            params["Limit"] = 150
            params["SortBy"] = "Random"

        async def run_query(p: dict[str, Any]) -> list[dict]:
            data = await self._vault.api("GET", "/Items", params=p)
            return list(data.get("Items") or [])

        try:
            items = await run_query(params)
        except RuntimeError:
            if params.get("SortBy") == "Random":
                params["SortBy"] = "SortName"
                items = await run_query(params)
            else:
                raise

        if (
            search_genre
            and search_genre not in ("All", "Recently Added")
            and not items
            and search_genre != genre_name
        ):
            params2 = dict(params)
            params2["Genres"] = genre_name
            items = await run_query(params2)

        return items

    async def resolve_item_for_tmdb(self, movie_id: str) -> Any:
        params = {"Fields": "Name,OriginalTitle,ProductionYear"}
        try:
            data = await self._vault.api("GET", f"/Items/{movie_id}", params=params)
        except RuntimeError:
            # Some servers reject global item lookup for ids that still appear in deck payloads.
            try:
                uid = await self._vault.delegate_user_id()
                data = await self._vault.api(
                    "GET", f"/Users/{uid}/Items/{movie_id}", params=params
                )
            except RuntimeError as exc:
                raise RuntimeError("Jellyfin item lookup failed") from exc
        title = data.get("Name") or data.get("OriginalTitle") or ""
        year = data.get("ProductionYear")
        if not title:
            raise RuntimeError("Jellyfin item lookup failed")
        return SimpleNamespace(title=title, year=year)

    async def server_info(self) -> dict:
        try:
            j = await self._vault.api("GET", "/System/Info")
            return {
                "machineIdentifier": j.get("ServerId") or j.get("Id") or "",
                "name": j.get("ServerName") or "Jellyfin",
                "webUrl": self._vault.client.base_url,
            }
        except RuntimeError:
            resp = await self._vault.client.request(
                "GET",
                "/System/Info/Public",
                timeout=15,
            )
            try:
                pub = resp.json()
            except ValueError:
                pub = {}
            return {
                "machineIdentifier": pub.get("Id") or "",
                "name": pub.get("ServerName") or "Jellyfin",
                "webUrl": self._vault.client.base_url,
            }

    async def fetch_library_image(self, path: str) -> tuple[bytes, str]:
        m = _JF_IMAGE_PATH.match(path)
        if not m:
            raise PermissionError("Invalid Jellyfin image path")
        iid = m.group(1)
        await self._vault.ensure_authenticated()
        url_path = f"/Items/{iid}/Images/Primary"

        max_attempts = 3

        async def _get() -> Any:
            return await self._vault.client.request(
                "GET",
                url_path,
                params={"maxHeight": 720},
                headers=self._vault.auth_header(),
                timeout=60,
            )

        async def _get_with_retry(label: str) -> Any:
            for attempt in range(1, max_attempts + 1):
                try:
                    return await _get()
                except Exception as exc:
                    if attempt == max_attempts:
                        raise
                    logger.warning(
                        "fetch_library_image: transient error on %s attempt %d/%d for %s: %s",
                        label,
                        attempt,
                        max_attempts,
                        iid,
                        exc,
                    )
                    await asyncio.sleep(0.5 * attempt)

        r = await _get_with_retry("attempt")

        if r.status_code == 401:
            await self._vault.reset()
            await self._vault.ensure_authenticated()
            r = await _get_with_retry("retry attempt")
        if r.status_code == 403:
            raise PermissionError("Jellyfin image forbidden")
        if r.status_code == 404:
            raise FileNotFoundError("Jellyfin image not found")
        if not r.is_success:
            raise RuntimeError(f"Jellyfin image fetch failed (HTTP {r.status_code})")
        ctype = r.headers.get("Content-Type") or "image/jpeg"
        return r.content, ctype


__all__ = ["JellyfinLibrary"]
