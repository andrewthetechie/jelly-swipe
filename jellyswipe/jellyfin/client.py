"""Async Jellyfin HTTP transport.

A thin ``httpx.AsyncClient`` wrapper that owns the base URL, MediaBrowser
Authorization header construction, and JSON decoding. It is intentionally
transport-only: token lifecycle and 401-re-auth live in
:class:`jellyswipe.jellyfin.vault.JellyfinVault`, and the role classes
(Vault / Library / Watchlist) each consume the same shared client.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_DEVICE_ID = "jelly-swipe-jellyfin-v1"
_DEFAULT_USER_AGENT = "JellySwipe/1.6 (+https://github.com/andrewthetechie/jelly-swipe)"
DEFAULT_TIMEOUT = 90.0


def media_browser_header(device_id: str, access_token: str) -> str:
    """Build the MediaBrowser Authorization header value."""
    return (
        'MediaBrowser Client="JellySwipe", Device="FlaskApp", '
        f'DeviceId="{device_id}", Version="1.0.0", Token="{access_token}"'
    )


class JellyfinClient:
    """Async HTTP transport for Jellyfin REST calls.

    Args:
        base_url: Jellyfin server base URL (trailing slash optional).
        device_id: Device identifier sent in the MediaBrowser header.
        timeout: Default request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        device_id: str = DEFAULT_DEVICE_ID,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._device_id = device_id
        self._timeout = timeout
        self._http = httpx.AsyncClient(timeout=timeout, transport=transport)

    @property
    def base_url(self) -> str:
        return self._base

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def http(self) -> httpx.AsyncClient:
        return self._http

    def auth_header(self, access_token: str) -> dict[str, str]:
        """Return an Authorization header for the given token."""
        return {"Authorization": media_browser_header(self._device_id, access_token)}

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Perform an HTTP request and return the raw response.

        Does not raise on HTTP errors — callers interpret status codes so they
        can implement role-specific handling (e.g. the vault's 401-retry, or
        the image proxy's 403/404 mapping).
        """
        url = f"{self._base}{path}"
        req_headers = dict(headers or {})
        req_headers.setdefault("Content-Type", "application/json")
        req_headers.setdefault("User-Agent", _DEFAULT_USER_AGENT)
        return await self._http.request(
            method,
            url,
            params=params,
            json=json_body,
            headers=req_headers,
            timeout=timeout if timeout is not None else self._timeout,
        )

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        await self._http.aclose()


__all__ = ["DEFAULT_DEVICE_ID", "JellyfinClient", "media_browser_header"]
