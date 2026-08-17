"""Jellyfin vault — delegate token and delegate user resolution.

Resolves ADR-0001's "per-user-token" semantic remnant: there is only ever ONE
Jellyfin access token in this application — the *server delegate token* set
from the operator-provided ``JELLYFIN_API_KEY``. Every authenticated browser
session acts as that delegate user against Jellyfin, so there are no per-user
tokens (see CONTEXT.md). This vault owns that single token's lifecycle plus
delegate user-id resolution, and provides the authenticated request helper
(``api``) with the 401 → reset → re-auth → single-retry behavior that the
legacy provider implemented.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from jellyswipe.jellyfin.client import DEFAULT_DEVICE_ID

if TYPE_CHECKING:
    from jellyswipe.jellyfin.client import JellyfinClient

logger = logging.getLogger(__name__)


class JellyfinVault:
    """Holds the delegate token and resolves the delegate user id."""

    def __init__(
        self,
        client: JellyfinClient,
        api_key: str = "",
        device_id: str = DEFAULT_DEVICE_ID,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._device_id = device_id
        self._access_token: str | None = None
        self._cached_user_id: str | None = None

    @property
    def client(self) -> JellyfinClient:
        return self._client

    async def ensure_authenticated(self) -> None:
        if self._access_token is None:
            await self._login_from_env()
            await self._verify_items()

    async def reset(self) -> None:
        self._access_token = None
        self._cached_user_id = None

    async def delegate_token(self) -> str:
        """Return the server delegate access token.

        Raises:
            RuntimeError: if no API key is configured.
        """
        await self.ensure_authenticated()
        if not self._access_token:
            raise RuntimeError("Jellyfin authentication failed (missing credentials)")
        return self._access_token

    async def delegate_user_id(self) -> str:
        """Return the delegate user's Jellyfin user id."""
        await self.ensure_authenticated()
        return await self._user_id()

    def auth_header(self, token: str | None = None) -> dict[str, str]:
        """Build an Authorization header for the given token (defaults to the delegate token)."""
        access_token = token if token is not None else (self._access_token or "")
        return self._client.auth_header(access_token)

    async def api(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: Any = None,
        retry: bool = True,
    ) -> dict:
        """Perform an authenticated request with 401 → reset → re-auth → single retry.

        Raises:
            RuntimeError: on non-2xx responses or non-JSON bodies.
        """
        await self.ensure_authenticated()
        resp = await self._client.request(
            method,
            path,
            params=params,
            json_body=json_body,
            headers=self.auth_header(),
        )
        if resp.status_code == 401 and retry:
            await self.reset()
            await self.ensure_authenticated()
            return await self.api(
                method, path, params=params, json_body=json_body, retry=False
            )
        if not resp.is_success:
            raise RuntimeError(f"Jellyfin request failed (HTTP {resp.status_code})")
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError as exc:
            raise RuntimeError("Jellyfin returned non-JSON body") from exc

    async def _login_from_env(self) -> None:
        if self._api_key:
            self._access_token = self._api_key
        else:
            raise RuntimeError("Jellyfin authentication failed (api_key required)")

    async def _verify_items(self) -> None:
        """Lightweight /Items probe after login (must not call api → avoid ensure loop)."""
        if not self._access_token:
            return
        resp = await self._client.request(
            "GET",
            "/Items",
            params={"Limit": 1},
            headers=self.auth_header(),
            timeout=30,
        )
        if resp.status_code == 401:
            raise RuntimeError("Jellyfin authentication failed (unauthorized)")
        if not resp.is_success:
            raise RuntimeError(
                f"Jellyfin authentication failed (HTTP {resp.status_code})"
            )

    async def _user_id(self) -> str:
        if self._cached_user_id:
            return self._cached_user_id
        try:
            data = await self.api("GET", "/Users/Me")
            uid = data.get("Id")
            if uid:
                self._cached_user_id = uid
                return uid
        except RuntimeError:
            pass

        # Some servers return 400 for /Users/Me when using API keys.
        resp = await self._client.request(
            "GET", "/Users", headers=self.auth_header(), timeout=30
        )
        if not resp.is_success:
            raise RuntimeError(
                f"Jellyfin: could not resolve user id (HTTP {resp.status_code})"
            )
        try:
            users = resp.json() or []
        except ValueError as exc:
            raise RuntimeError(
                "Jellyfin: could not resolve user id (invalid JSON)"
            ) from exc
        if users and users[0].get("Id"):
            self._cached_user_id = users[0]["Id"]
            return self._cached_user_id
        raise RuntimeError("Jellyfin: could not resolve current user id")


__all__ = ["JellyfinVault"]
