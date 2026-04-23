"""Jellyfin REST client and LibraryMediaProvider (auth + library parity)."""

from __future__ import annotations

import os
import random
import re
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import requests

from media_provider.base import LibraryMediaProvider

_DEVICE_ID = os.getenv("JELLYFIN_DEVICE_ID", "kino-swipe-jellyfin-v1")

# Allowlisted proxy path: jellyfin/{item_id}/Primary
# Accept both canonical UUID and 32-char hex ids returned by Jellyfin.
_JF_IMAGE_PATH = re.compile(r"^jellyfin/([0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$")


def _media_browser_header(access_token: str) -> str:
    return (
        'MediaBrowser Client="KinoSwipe", Device="FlaskApp", '
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


class JellyfinLibraryProvider(LibraryMediaProvider):
    """Jellyfin-backed library: genres, deck, images, TMDB item resolution, server info."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"
        self._access_token: Optional[str] = None
        self._cached_user_id: Optional[str] = None
        self._cached_library_id: Optional[str] = None
        self._genre_cache: Optional[List[str]] = None

    def reset(self) -> None:
        self._access_token = None
        self._cached_user_id = None
        self._cached_library_id = None
        self._genre_cache = None
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def ensure_authenticated(self) -> None:
        if self._access_token is None:
            self._login_from_env()
            self._verify_items()

    def _login_from_env(self) -> None:
        api_key = os.getenv("JELLYFIN_API_KEY", "").strip()
        username = os.getenv("JELLYFIN_USERNAME", "").strip()
        password = os.getenv("JELLYFIN_PASSWORD", "").strip()

        if api_key:
            self._access_token = api_key
        elif username and password:
            url = f"{self._base}/Users/AuthenticateByName"
            init_header = (
                'MediaBrowser Client="KinoSwipe", Device="FlaskApp", '
                f'DeviceId="{_DEVICE_ID}", Version="1.0.0", Token=""'
            )
            try:
                r = self._session.post(
                    url,
                    headers={"Authorization": init_header},
                    json={"Username": username, "Pw": password},
                    timeout=30,
                )
            except requests.RequestException as exc:
                raise RuntimeError("Jellyfin authentication failed (network error)") from exc
            if not r.ok:
                raise RuntimeError(
                    "Jellyfin authentication failed (check username, password, or server URL)"
                )
            try:
                data = r.json()
            except ValueError as exc:
                raise RuntimeError("Jellyfin authentication failed (invalid response)") from exc
            token = data.get("AccessToken")
            if not token:
                raise RuntimeError("Jellyfin authentication failed (no access token in response)")
            self._access_token = token
        else:
            raise RuntimeError("Jellyfin authentication failed (missing credentials)")

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
            return self._api(method, path, params=params, json_body=json_body, retry=False)
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
            raise RuntimeError("Jellyfin: could not resolve user id (network error)") from exc
        if not r.ok:
            raise RuntimeError(f"Jellyfin: could not resolve user id (HTTP {r.status_code})")
        users = r.json() or []
        preferred = (os.getenv("JELLYFIN_USERNAME") or "").strip().lower()
        for u in users:
            if preferred and (u.get("Name") or "").strip().lower() == preferred and u.get("Id"):
                self._cached_user_id = u["Id"]
                return self._cached_user_id
        if users and users[0].get("Id"):
            self._cached_user_id = users[0]["Id"]
            return self._cached_user_id
        raise RuntimeError("Jellyfin: could not resolve current user id")

    def _movies_library_id(self) -> str:
        if self._cached_library_id:
            return self._cached_library_id
        uid = self._user_id()
        data = self._api("GET", f"/Users/{uid}/Views")
        for v in data.get("Items") or []:
            ct = (v.get("CollectionType") or "").lower()
            if ct == "movies":
                lid = v.get("Id")
                if lid:
                    self._cached_library_id = lid
                    return lid
        raise RuntimeError(
            "Jellyfin: no library with CollectionType=movies — add a Movies library on the server."
        )

    def list_genres(self) -> List[str]:
        if self._genre_cache is not None:
            return self._genre_cache
        lib = self._movies_library_id()
        uid = self._user_id()
        names: List[str] = []

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

        if not names:
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
        self._genre_cache = display
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
        }

    def fetch_deck(self, genre_name: Optional[str] = None) -> List[dict]:
        lib = self._movies_library_id()
        uid = self._user_id()
        params: Dict[str, Any] = {
            "ParentId": lib,
            "UserId": uid,
            "IncludeItemTypes": "Movie",
            "Recursive": "true",
            "Fields": "Overview,RunTimeTicks,ProductionYear,CommunityRating,CriticRating",
        }

        do_shuffle = True
        search_genre = "Science Fiction" if genre_name == "Sci-Fi" else genre_name

        if genre_name == "Recently Added":
            params["Limit"] = 100
            params["SortBy"] = "DateCreated"
            params["SortOrder"] = "Descending"
            do_shuffle = False
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
                do_shuffle = True
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

        movie_list = [self._item_to_card(it) for it in items]

        if do_shuffle:
            random.shuffle(movie_list)
        return movie_list

    def resolve_item_for_tmdb(self, movie_id: str) -> Any:
        data = self._api(
            "GET",
            f"/Items/{movie_id}",
            params={"Fields": "Name,OriginalTitle,ProductionYear"},
        )
        title = data.get("Name") or data.get("OriginalTitle") or ""
        year = data.get("ProductionYear")
        return SimpleNamespace(title=title, year=year)

    def server_info(self) -> dict:
        try:
            j = self._api("GET", "/System/Info")
            return {
                "machineIdentifier": j.get("ServerId") or j.get("Id") or "",
                "name": j.get("ServerName") or "Jellyfin",
            }
        except RuntimeError:
            r = requests.get(f"{self._base}/System/Info/Public", timeout=15)
            r.raise_for_status()
            pub = r.json()
            return {
                "machineIdentifier": pub.get("Id") or "",
                "name": pub.get("ServerName") or "Jellyfin",
            }

    def fetch_library_image(self, path: str) -> Tuple[bytes, str]:
        m = _JF_IMAGE_PATH.match(path)
        if not m:
            raise PermissionError("Invalid Jellyfin image path")
        iid = m.group(1)
        self.ensure_authenticated()
        url = f"{self._base}/Items/{iid}/Images/Primary"
        r = self._session.get(
            url,
            params={"maxHeight": 720},
            headers=self._auth_headers(),
            timeout=60,
        )
        if r.status_code == 401:
            self.reset()
            self.ensure_authenticated()
            r = self._session.get(
                url,
                params={"maxHeight": 720},
                headers=self._auth_headers(),
                timeout=60,
            )
        if r.status_code == 403:
            raise PermissionError("Jellyfin image forbidden")
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
            'MediaBrowser Client="KinoSwipe", Device="Browser", '
            f'DeviceId="{_DEVICE_ID}", Version="1.0.0", Token="{user_token}"'
        )

    def authenticate_user_session(self, username: str, password: str) -> dict:
        """Exchange user credentials for Jellyfin user session token + user id."""
        if not username or not password:
            raise RuntimeError("Jellyfin login failed (missing username/password)")
        url = f"{self._base}/Users/AuthenticateByName"
        init_header = (
            'MediaBrowser Client="KinoSwipe", Device="Browser", '
            f'DeviceId="{_DEVICE_ID}", Version="1.0.0", Token=""'
        )
        try:
            r = self._session.post(
                url,
                headers={"Authorization": init_header, "Content-Type": "application/json"},
                json={"Username": username, "Pw": password},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise RuntimeError("Jellyfin login failed (network error)") from exc
        if not r.ok:
            raise RuntimeError("Jellyfin login failed (invalid credentials)")
        data = r.json()
        token = data.get("AccessToken")
        user = data.get("User") or {}
        uid = user.get("Id")
        if not token or not uid:
            raise RuntimeError("Jellyfin login failed (missing token or user id)")
        return {"token": token, "user_id": uid}

    def resolve_user_id_from_token(self, user_token: str) -> str:
        if not user_token:
            raise RuntimeError("Missing Jellyfin user token")
        url = f"{self._base}/Users/Me"
        headers = {"Authorization": self.user_auth_header(user_token)}
        try:
            r = self._session.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError("Failed to resolve Jellyfin user (network error)") from exc
        if r.status_code in (401, 403):
            raise RuntimeError("Jellyfin user token unauthorized")
        if r.status_code == 400:
            # API-key style tokens may not support /Users/Me.
            try:
                rr = self._session.get(f"{self._base}/Users", headers=headers, timeout=30)
            except requests.RequestException as exc:
                raise RuntimeError("Failed to resolve Jellyfin user (network error)") from exc
            if not rr.ok:
                raise RuntimeError(f"Failed to resolve Jellyfin user (HTTP {rr.status_code})")
            users = rr.json() or []
            preferred = (os.getenv("JELLYFIN_USERNAME") or "").strip().lower()
            for u in users:
                if preferred and (u.get("Name") or "").strip().lower() == preferred and u.get("Id"):
                    return u["Id"]
            if users and users[0].get("Id"):
                return users[0]["Id"]
            raise RuntimeError("Failed to resolve Jellyfin user id")
        if not r.ok:
            raise RuntimeError(f"Failed to resolve Jellyfin user (HTTP {r.status_code})")
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
