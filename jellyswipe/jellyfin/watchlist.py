"""Jellyfin watchlist writer — add-to-favorites.

Resolves ADR-0001's semantic remnant: the legacy ``add_to_user_favorites``
took a ``user_token`` and resolved a user id from it, implying per-user
tokens that no longer exist. Today every authenticated session acts as the
single server *delegate user*, so the writer simply uses the vault's delegate
token and delegate user id. See ``JellyfinVault`` and CONTEXT.md.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jellyswipe.jellyfin.vault import JellyfinVault

logger = logging.getLogger(__name__)


class JellyfinWatchlistWriter:
    """Adds media to the delegate user's Jellyfin favourites/watchlist."""

    def __init__(self, vault: JellyfinVault) -> None:
        self._vault = vault

    async def add_to_favorites(self, media_id: str) -> None:
        """Add ``media_id`` to the delegate user's favourites.

        The token used is always the server delegate token held by the vault
        (there are no per-user tokens — see ADR-0001 / CONTEXT.md).

        Raises:
            RuntimeError: on network failure or an unauthorized/error response.
        """
        uid = await self._vault.delegate_user_id()
        resp = await self._vault.client.request(
            "POST",
            f"/Users/{uid}/FavoriteItems/{media_id}",
            headers=self._vault.auth_header(),
            timeout=30,
        )
        if resp.status_code in (401, 403):
            raise RuntimeError("Jellyfin favorite add unauthorized")
        if not resp.is_success:
            raise RuntimeError(
                f"Jellyfin favorite add failed (HTTP {resp.status_code})"
            )


__all__ = ["JellyfinWatchlistWriter"]
