"""Jellyfin REST client (auth + library parity)."""

from __future__ import annotations

import logging
import os
import random
import re
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


_DEVICE_ID = os.getenv("JELLYFIN_DEVICE_ID", "jelly-swipe-jellyfin-v1")

# Allowlisted proxy path: jellyfin/{item_id}/Primary
# Accept both canonical UUID and 32-char hex ids returned by Jellyfin.
_JF_IMAGE_PATH = re.compile(r"^jellyfin/([0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$")


def _media_browser_header(access_token: str) -> str:
    return (
        'MediaBrowser Client="JellySwipe", Device="FlaskApp", '
        f'DeviceId="{_DEVICE_ID}", Version="1.0.0", Token="{access_token}"'
    )


def _format_runtime(seconds: int) -> str:
    if seconds <= 0:
        return ""
    hrs, rem = divmod(seconds, 3600)
    mins = rem // 60
    if hrs > 0:
        return f"{hrs}h {mins}m"
    return f"{mins}m"


class JellyfinLibraryProvider:
    """Jellyfin-backed library: genres, deck, images, TMDB item resolution, server info."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"
        self._access_token: Optional[str] = None
        self._cached_user_id: Optional[str] = None
        self._cached_library_ids: Dict[str, List[str]] = {}
        self._genre_cache: Dict[str, List[str]] = {}

    def reset(self) -> None:
        self._access_token = None
        self._cached_user_id = None
        self._cached_library_ids = {}
        self._genre_cache = {}
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def ensure_authenticated(self) -> None:
        if self._access_token is None:
            self._login_from_env()
            self._verify_items()

    def server_access_token_for_delegate(self) -> str:
        """
        For in-process Flask request handling only — not for JSON responses.
        """
        self.ensure_authenticated()
        if not self._access_token:
            raise RuntimeError("Jellyfin authentication failed (missing credentials)")
        return self._access_token

    def server_primary_user_id_for_delegate(self) -> str:
        self.ensure_authenticated()
        return self._user_id()

    def _login_from_env(self) -> None:
        api_key = os.getenv("JELLYFIN_API_KEY", "").strip()
        if api_key:
            self._access_token = api_key
        else:
            raise RuntimeError(
                "Jellyfin authentication failed (JELLYFIN_API_KEY required)"
            )

    def _verify_items(self) -> None:
        """Lightweight /Items probe after login (must not call _api → ensure loop)."""
        if not self._access_token:
            return
        url = f"{self._base}/Items"
        r = self._session.get(
            url,
            params={"Limit": 1},
            headers=self._auth_headers(),
            timeout=30,
        )
        if r.status_code == 401:
            raise RuntimeError("Jellyfin authentication failed (unauthorized)")
        if not r.ok:
            raise RuntimeError(f"Jellyfin authentication failed (HTTP {r.status_code})")

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": _media_browser_header(self._access_token or "")}

    def _api(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Any = None,
        retry: bool = True,
    ) -> dict:
        self.ensure_authenticated()
        url = f"{self._base}{path}"
        r = self._session.request(
            method,
            url,
            params=params,
            json=json_body,
            headers=self._auth_headers(),
            timeout=90,
        )
        if r.status_code == 401 and retry:
            self.reset()
            self.ensure_authenticated()
            return self._api(
                method, path, params=params, json_body=json_body, retry=False
            )
        if not r.ok:
            raise RuntimeError(f"Jellyfin request failed (HTTP {r.status_code})")
        if not r.content:
            return {}
        try:
            return r.json()
        except ValueError as exc:
            raise RuntimeError("Jellyfin returned non-JSON body") from exc

    def _user_id(self) -> str:
        if self._cached_user_id:
            return self._cached_user_id
        try:
            data = self._api("GET", "/Users/Me")
            uid = data.get("Id")
            if uid:
                self._cached_user_id = uid
                return uid
        except RuntimeError:
            pass

        # Some servers return 400 for /Users/Me when using API keys.
        url = f"{self._base}/Users"
        try:
            r = self._session.get(url, headers=self._auth_headers(), timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(
                "Jellyfin: could not resolve user id (network error)"
            ) from exc
        if not r.ok:
            raise RuntimeError(
                f"Jellyfin: could not resolve user id (HTTP {r.status_code})"
            )
        users = r.json() or []
        if users and users[0].get("Id"):
            self._cached_user_id = users[0]["Id"]
            return self._cached_user_id
        raise RuntimeError("Jellyfin: could not resolve current user id")

    def _library_ids_for_type(self, collection_type: str) -> List[str]:
        """Return all library IDs matching the given collection type."""
        if collection_type in self._cached_library_ids:
            return self._cached_library_ids[collection_type]

        uid = self._user_id()
        data = self._api("GET", f"/Users/{uid}/Views")
        ids: List[str] = []
        for v in data.get("Items") or []:
            ct = (v.get("CollectionType") or "").lower()
            if ct == collection_type.lower():
                lid = v.get("Id")
                if lid:
                    ids.append(lid)

        self._cached_library_ids[collection_type] = ids
        return ids

    def _movies_library_id(self) -> str:
        """Legacy method for backward compatibility — returns first movies library."""
        ids = self._library_ids_for_type("movies")
        if not ids:
            raise RuntimeError(
                "Jellyfin: no library with CollectionType=movies — add a Movies library on the server."
            )
        return ids[0]

    def list_genres(self) -> List[str]:
        cache_key = "all"
        if cache_key in self._genre_cache:
            return self._genre_cache[cache_key]

        uid = self._user_id()
        names: List[str] = []

        # Query genres from movie libraries
        movie_libs = self._library_ids_for_type("movies")
        for lib in movie_libs:
            data = self._api(
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
        tv_libs = self._library_ids_for_type("tvshows")
        for lib in tv_libs:
            data = self._api(
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
                    gdata = self._api(
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
        display = ["Sci-Fi" if n == "Science Fiction" else n for n in names]
        self._genre_cache[cache_key] = display
        return display

    def _item_to_card(self, it: dict) -> dict:
        mid = it.get("Id")
        ticks = int(it.get("RunTimeTicks") or 0)
        seconds = ticks // 10_000_000 if ticks else 0
        rating = it.get("CommunityRating")
        if rating is None:
            rating = it.get("CriticRating")
        return {
            "id": mid,
            "title": it.get("Name") or "",
            "summary": it.get("Overview") or "",
            "thumb": f"/proxy?path=jellyfin/{mid}/Primary",
            "rating": rating,
            "duration": _format_runtime(seconds),
            "year": it.get("ProductionYear"),
            "media_type": "movie",
        }

    def _series_to_card(self, it: dict) -> dict:
        """Transform a TV Series item to a card."""
        mid = it.get("Id")
        return {
            "id": mid,
            "title": it.get("Name") or "",
            "summary": it.get("Overview") or "",
            "thumb": f"/proxy?path=jellyfin/{mid}/Primary",
            "year": it.get("ProductionYear"),
            "media_type": "tv_show",
            "season_count": it.get("ChildCount"),
        }

    def fetch_deck(
        self,
        media_types: List[str],
        genre_name: Optional[str] = None,
        hide_watched: bool = False,
    ) -> List[dict]:
        """Fetch deck cards for the specified media types.

        Args:
            media_types: List of media types to fetch ("movie", "tv_show").
            genre_name: Optional genre filter.
            hide_watched: When True, filter out watched items via Jellyfin's Filters=IsNotPlayed.

        Returns:
            List of card dicts with media_type field set.
        """
        uid = self._user_id()
        all_items: List[dict] = []

        # Fetch movies
        if "movie" in media_types:
            movie_libs = self._library_ids_for_type("movies")
            for lib in movie_libs:
                items = self._fetch_items_for_library(
                    lib=lib,
                    uid=uid,
                    item_type="Movie",
                    genre_name=genre_name,
                    hide_watched=hide_watched,
                )
                all_items.extend(items)

        # Fetch TV shows
        if "tv_show" in media_types:
            tv_libs = self._library_ids_for_type("tvshows")
            for lib in tv_libs:
                items = self._fetch_items_for_library(
                    lib=lib,
                    uid=uid,
                    item_type="Series",
                    genre_name=genre_name,
                    hide_watched=hide_watched,
                )
                all_items.extend(items)

        # Transform items to cards
        cards: List[dict] = []
        for it in all_items:
            item_type = it.get("Type", "")
            if item_type == "Series":
                cards.append(self._series_to_card(it))
            else:
                cards.append(self._item_to_card(it))

        # Shuffle if not recently added
        search_genre = "Science Fiction" if genre_name == "Sci-Fi" else genre_name
        if search_genre not in ("Recently Added", None, "All"):
            random.shuffle(cards)

        return cards

    def _fetch_items_for_library(
        self,
        lib: str,
        uid: str,
        item_type: str,
        genre_name: Optional[str],
        hide_watched: bool = False,
    ) -> List[dict]:
        """Fetch items from a single library."""
        params: Dict[str, Any] = {
            "ParentId": lib,
            "UserId": uid,
            "IncludeItemTypes": item_type,
            "Recursive": "true",
            "Fields": "Overview,RunTimeTicks,ProductionYear,CommunityRating,CriticRating,ChildCount",
        }

        # Add Filters=IsNotPlayed when hide_watched is True
        if hide_watched:
            params["Filters"] = "IsNotPlayed"

        search_genre = "Science Fiction" if genre_name == "Sci-Fi" else genre_name

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

        def run_query(p: Dict[str, Any]) -> List[dict]:
            data = self._api("GET", "/Items", params=p)
            return list(data.get("Items") or [])

        try:
            items = run_query(params)
        except RuntimeError:
            if params.get("SortBy") == "Random":
                params["SortBy"] = "SortName"
                items = run_query(params)
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
            items = run_query(params2)

        return items

    def resolve_item_for_tmdb(self, movie_id: str) -> Any:
        params = {"Fields": "Name,OriginalTitle,ProductionYear"}
        try:
            data = self._api("GET", f"/Items/{movie_id}", params=params)
        except RuntimeError:
            # Some servers reject global item lookup for ids that still appear in deck payloads.
            try:
                uid = self._user_id()
                data = self._api("GET", f"/Users/{uid}/Items/{movie_id}", params=params)
            except RuntimeError as exc:
                raise RuntimeError("Jellyfin item lookup failed") from exc
        title = data.get("Name") or data.get("OriginalTitle") or ""
        year = data.get("ProductionYear")
        if not title:
            raise RuntimeError("Jellyfin item lookup failed")
        return SimpleNamespace(title=title, year=year)

    def server_info(self) -> dict:
        try:
            j = self._api("GET", "/System/Info")
            return {
                "machineIdentifier": j.get("ServerId") or j.get("Id") or "",
                "name": j.get("ServerName") or "Jellyfin",
                "webUrl": self._base,
            }
        except RuntimeError:
            response = self._session.get(
                f"{self._base}/System/Info/Public",
                timeout=(5, 15),
            )
            pub = response.json()
            return {
                "machineIdentifier": pub.get("Id") or "",
                "name": pub.get("ServerName") or "Jellyfin",
                "webUrl": self._base,
            }

    def fetch_library_image(self, path: str) -> Tuple[bytes, str]:
        m = _JF_IMAGE_PATH.match(path)
        if not m:
            raise PermissionError("Invalid Jellyfin image path")
        iid = m.group(1)
        self.ensure_authenticated()
        url = f"{self._base}/Items/{iid}/Images/Primary"

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                r = self._session.get(
                    url,
                    params={"maxHeight": 720},
                    headers=self._auth_headers(),
                    timeout=60,
                )
                break
            except requests.exceptions.RequestException as exc:
                if attempt == max_attempts:
                    raise
                logger.warning(
                    "fetch_library_image: transient error on attempt %d/%d for %s: %s",
                    attempt,
                    max_attempts,
                    iid,
                    exc,
                )
                time.sleep(0.5 * attempt)

        if r.status_code == 401:
            self.reset()
            self.ensure_authenticated()
            for attempt in range(1, max_attempts + 1):
                try:
                    r = self._session.get(
                        url,
                        params={"maxHeight": 720},
                        headers=self._auth_headers(),
                        timeout=60,
                    )
                    break
                except requests.exceptions.RequestException as exc:
                    if attempt == max_attempts:
                        raise
                    logger.warning(
                        "fetch_library_image: transient error on retry attempt %d/%d for %s: %s",
                        attempt,
                        max_attempts,
                        iid,
                        exc,
                    )
                    time.sleep(0.5 * attempt)
        if r.status_code == 403:
            raise PermissionError("Jellyfin image forbidden")
        if r.status_code == 404:
            raise FileNotFoundError("Jellyfin image not found")
        if not r.ok:
            raise RuntimeError(f"Jellyfin image fetch failed (HTTP {r.status_code})")
        ctype = r.headers.get("Content-Type") or "image/jpeg"
        return r.content, ctype

    @staticmethod
    def extract_media_browser_token(auth_header: str) -> Optional[str]:
        """Extract Token=\"...\" from Authorization: MediaBrowser ... header."""
        if not auth_header:
            return None
        m = re.search(r'Token="([^"]+)"', auth_header)
        return m.group(1) if m else None

    @staticmethod
    def user_auth_header(user_token: str) -> str:
        return (
            'MediaBrowser Client="JellySwipe", Device="Browser", '
            f'DeviceId="{_DEVICE_ID}", Version="1.0.0", Token="{user_token}"'
        )

    def resolve_user_id_from_token(self, user_token: str) -> str:
        if not user_token:
            raise RuntimeError("Missing Jellyfin user token")
        url = f"{self._base}/Users/Me"
        headers = {"Authorization": self.user_auth_header(user_token)}
        try:
            r = self._session.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(
                "Failed to resolve Jellyfin user (network error)"
            ) from exc
        if r.status_code in (401, 403):
            raise RuntimeError("Jellyfin user token unauthorized")
        if r.status_code == 400:
            # API-key style tokens may not support /Users/Me.
            try:
                rr = self._session.get(
                    f"{self._base}/Users", headers=headers, timeout=30
                )
            except requests.RequestException as exc:
                raise RuntimeError(
                    "Failed to resolve Jellyfin user (network error)"
                ) from exc
            if not rr.ok:
                raise RuntimeError(
                    f"Failed to resolve Jellyfin user (HTTP {rr.status_code})"
                )
            users = rr.json() or []
            if users and users[0].get("Id"):
                return users[0]["Id"]
            raise RuntimeError("Failed to resolve Jellyfin user id")
        if not r.ok:
            raise RuntimeError(
                f"Failed to resolve Jellyfin user (HTTP {r.status_code})"
            )
        data = r.json()
        uid = data.get("Id")
        if not uid:
            raise RuntimeError("Failed to resolve Jellyfin user id")
        return uid

    def add_to_user_favorites(self, user_token: str, movie_id: str) -> None:
        user_id = self.resolve_user_id_from_token(user_token)
        url = f"{self._base}/Users/{user_id}/FavoriteItems/{movie_id}"
        headers = {"Authorization": self.user_auth_header(user_token)}
        try:
            r = self._session.post(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError("Jellyfin favorite add failed (network error)") from exc
        if r.status_code in (401, 403):
            raise RuntimeError("Jellyfin favorite add unauthorized")
        if not r.ok:
            raise RuntimeError(f"Jellyfin favorite add failed (HTTP {r.status_code})")
