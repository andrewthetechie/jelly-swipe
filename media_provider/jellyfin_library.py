"""Jellyfin REST client and LibraryMediaProvider (Phase 3: auth + HTTP only)."""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import requests

from media_provider.base import LibraryMediaProvider

# Stable device id for Jellyfin session tracking (override via env if needed).
_DEVICE_ID = os.getenv("JELLYFIN_DEVICE_ID", "kino-swipe-jellyfin-v1")


def _media_browser_header(access_token: str) -> str:
    return (
        'MediaBrowser Client="KinoSwipe", Device="FlaskApp", '
        f'DeviceId="{_DEVICE_ID}", Version="1.0.0", Token="{access_token}"'
    )


class JellyfinLibraryProvider(LibraryMediaProvider):
    """Authenticated Jellyfin access; library deck/genres/images land in Phase 4."""

    _phase4_msg = (
        "Jellyfin library browsing (deck, genres, images) is implemented in Phase 4 "
        "(library & media)."
    )

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"
        self._access_token: Optional[str] = None

    def reset(self) -> None:
        self._access_token = None
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def ensure_authenticated(self) -> None:
        """Obtain token (if needed) and verify with a minimal /Items request."""
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
        url = f"{self._base}/Items"
        headers = {"Authorization": _media_browser_header(self._access_token or "")}
        try:
            r = self._session.get(url, params={"Limit": 1}, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError("Jellyfin authentication failed (network error)") from exc
        if r.status_code == 401:
            raise RuntimeError("Jellyfin authentication failed (unauthorized)")
        if not r.ok:
            raise RuntimeError(
                f"Jellyfin authentication failed (HTTP {r.status_code})"
            )

    def list_genres(self) -> List[str]:
        return []

    def fetch_deck(self, genre_name: Optional[str] = None) -> List[dict]:
        raise RuntimeError(self._phase4_msg)

    def resolve_item_for_tmdb(self, movie_id: str):
        raise RuntimeError(self._phase4_msg)

    def server_info(self) -> dict:
        # Public endpoint — no secret token in URL; shape aligned with Plex keys for later phases.
        try:
            r = requests.get(f"{self._base}/System/Info/Public", timeout=15)
            r.raise_for_status()
            j = r.json()
        except requests.RequestException as exc:
            raise RuntimeError("Jellyfin server info unavailable") from exc
        return {
            "machineIdentifier": j.get("Id") or "",
            "name": j.get("ServerName") or "Jellyfin",
        }

    def fetch_library_image(self, path: str) -> Tuple[bytes, str]:
        raise PermissionError(self._phase4_msg)
