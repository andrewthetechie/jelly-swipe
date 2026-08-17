"""Tests for JellyfinWatchlistWriter (issue #299 role split).

The writer uses the vault's delegate token + delegate user id directly —
there are no per-user tokens (ADR-0001 resolution).
"""

import httpx
import pytest

from jellyswipe.jellyfin import JellyfinClient, JellyfinVault, JellyfinWatchlistWriter

BASE = "http://test.local"


def _build_writer(handler, *, token="test-token", user_id="user-123"):
    client = JellyfinClient(BASE, transport=httpx.MockTransport(handler))
    vault = JellyfinVault(client, api_key="test-api-key")
    vault._access_token = token
    vault._cached_user_id = user_id
    writer = JellyfinWatchlistWriter(vault)
    return client, vault, writer


def _ok(payload):
    return httpx.Response(200, json=payload)


@pytest.mark.anyio
async def test_add_to_favorites_posts_delegate_user_endpoint():
    """add_to_favorites POSTs to the delegate user's FavoriteItems endpoint."""
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        return _ok({})

    _, _, writer = _build_writer(handler)

    await writer.add_to_favorites("movie-1")

    assert seen["method"] == "POST"
    assert seen["path"] == "/Users/user-123/FavoriteItems/movie-1"


@pytest.mark.anyio
async def test_add_to_favorites_unauthorized_raises():
    """A 401/403 from Jellyfin raises RuntimeError (no per-user token misuse)."""

    def handler(request):
        return httpx.Response(403)

    _, _, writer = _build_writer(handler)

    with pytest.raises(RuntimeError):
        await writer.add_to_favorites("movie-1")


@pytest.mark.anyio
async def test_add_to_favorites_server_error_raises():
    """A non-2xx response raises RuntimeError."""

    def handler(request):
        return httpx.Response(500)

    _, _, writer = _build_writer(handler)

    with pytest.raises(RuntimeError):
        await writer.add_to_favorites("movie-1")
