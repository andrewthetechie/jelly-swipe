"""Tests for the split-by-role Jellyfin integration (issue #299).

Covers the async HTTP client, the JellyfinVault (delegate token + user
resolution), and the JellyfinLibrary (deck adapter) over an ``httpx.MockTransport``
so each role is exercised in isolation without a live server or the old
global singleton.
"""

from types import SimpleNamespace

import httpx
import pytest

from jellyswipe.jellyfin import JellyfinClient, JellyfinLibrary, JellyfinVault

BASE = "http://test.local"


def _build(
    handler,
    *,
    token="test-token",
    user_id="user-123",
    library_ids=None,
):
    """Build a client + vault + library over a MockTransport with seeded state."""
    client = JellyfinClient(BASE, transport=httpx.MockTransport(handler))
    vault = JellyfinVault(client, api_key="test-api-key")
    vault._access_token = token
    if user_id:
        vault._cached_user_id = user_id
    library = JellyfinLibrary(vault)
    if library_ids:
        library._cached_library_ids = library_ids
    return client, vault, library


def _ok(payload):
    return httpx.Response(200, json=payload)


# ---- Authentication / vault ----


@pytest.mark.anyio
async def test_auth_with_api_key_sets_token():
    """Vault sets the delegate token from the API key (with /Items probe)."""
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return _ok({"Items": []})

    client = JellyfinClient(BASE, transport=httpx.MockTransport(handler))
    vault = JellyfinVault(client, api_key="secret-key")

    token = await vault.delegate_token()

    assert token == "secret-key"
    assert vault._access_token == "secret-key"
    assert "/Items" in calls  # ensure_authenticated ran the lightweight probe


@pytest.mark.anyio
async def test_missing_api_key_raises():
    """delegate_token raises RuntimeError when no API key is configured."""
    client = JellyfinClient(BASE, transport=httpx.MockTransport(lambda r: _ok({})))
    vault = JellyfinVault(client, api_key="")

    with pytest.raises(RuntimeError):
        await vault.delegate_token()


@pytest.mark.anyio
async def test_401_triggers_reset_and_single_retry():
    """A 401 on api() resets the vault, re-authenticates, and retries once."""
    seq = []

    def handler(request):
        path = request.url.path
        seq.append(path)
        if path == "/System/Info" and seq.count("/System/Info") == 1:
            return httpx.Response(401)
        return _ok({"ServerName": "Jellyfin", "Id": "srv-1"})

    _, vault, _ = _build(handler, token="test-token", user_id=None)

    data = await vault.api("GET", "/System/Info")

    assert data["ServerName"] == "Jellyfin"
    # First attempt + one retry after re-auth
    assert seq.count("/System/Info") == 2
    assert "/Items" in seq  # re-auth probe ran


@pytest.mark.anyio
async def test_token_caching_prevents_redundant_auth():
    """With a token already set, api() performs only the requested call."""
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return _ok({"ServerName": "Jellyfin", "Id": "srv-1"})

    _, vault, _ = _build(handler, token="test-token", user_id=None)

    await vault.api("GET", "/System/Info")
    await vault.api("GET", "/System/Info")

    assert calls == ["/System/Info", "/System/Info"]
    assert "/Items" not in calls


# ---- User ID resolution ----


@pytest.mark.anyio
async def test_user_id_from_users_me_endpoint():
    """delegate_user_id resolves via /Users/Me."""

    def handler(request):
        if request.url.path == "/Users/Me":
            return _ok({"Id": "resolved-user"})
        return _ok({"Items": []})

    _, vault, _ = _build(handler, token="test-token", user_id=None)

    uid = await vault.delegate_user_id()
    assert uid == "resolved-user"


@pytest.mark.anyio
async def test_user_id_fallback_to_first_user():
    """When /Users/Me fails (400), fall back to the first user in /Users."""

    def handler(request):
        path = request.url.path
        if path == "/Users/Me":
            return httpx.Response(400)
        if path == "/Users":
            return _ok([{"Id": "first-user"}])
        return _ok({"Items": []})

    _, vault, _ = _build(handler, token="test-token", user_id=None)

    uid = await vault.delegate_user_id()
    assert uid == "first-user"


# ---- Library discovery ----


@pytest.mark.anyio
async def test_movies_library_id_finds_movies_collection():
    """_library_ids_for_type('movies') collects matching library IDs."""

    def handler(request):
        if request.url.path == "/Users/user-123/Views":
            return _ok(
                {
                    "Items": [
                        {"Id": "lib-a", "CollectionType": "movies"},
                        {"Id": "lib-b", "CollectionType": "tvshows"},
                        {"Id": "lib-c", "CollectionType": "Movies"},
                    ]
                }
            )
        return _ok({"Items": []})

    _, _, library = _build(handler)

    ids = await library._library_ids_for_type("movies")
    assert ids == ["lib-a", "lib-c"]


@pytest.mark.anyio
async def test_movies_library_id_raises_when_no_movies():
    """First movies library raises when no movie collection exists."""

    def handler(request):
        if request.url.path == "/Users/user-123/Views":
            return _ok({"Items": [{"Id": "lib-tv", "CollectionType": "tvshows"}]})
        return _ok({"Items": []})

    _, _, library = _build(handler)

    with pytest.raises(RuntimeError):
        await library._movies_library_id()


# ---- list_genres ----


@pytest.mark.anyio
async def test_list_genres_from_items_filters():
    """list_genres reads genre names from /Items/Filters for movie and TV libs."""

    def handler(request):
        if request.url.path == "/Items/Filters":
            it = request.url.params.get("IncludeItemTypes")
            return _ok(
                {
                    "GenreFilters": [
                        {"Name": "Action"},
                        {"Name": "Comedy"},
                    ]
                    if it == "Movie"
                    else [
                        {"Name": "Drama"},
                        {"Name": "Comedy"},
                    ]
                }
            )
        return _ok({"Items": []})

    _, _, library = _build(
        handler, library_ids={"movies": ["lib-m"], "tvshows": ["lib-tv"]}
    )

    genres = await library.list_genres()
    assert genres == ["Action", "Comedy", "Drama"]


@pytest.mark.anyio
async def test_genre_cache_prevents_redundant_api_calls():
    """A cached genre list avoids repeated /Items/Filters calls."""
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/Items/Filters":
            return _ok({"GenreFilters": [{"Name": "Action"}]})
        return _ok({"Items": []})

    _, _, library = _build(handler, library_ids={"movies": ["lib-m"]})

    await library.list_genres()
    await library.list_genres()

    assert calls.count("/Items/Filters") == 1


# ---- fetch_deck ----


@pytest.mark.anyio
async def test_fetch_deck_all_movies():
    """fetch_deck returns movie cards from the /Items query."""

    def handler(request):
        if request.url.path == "/Items":
            return _ok(
                {
                    "Items": [
                        {
                            "Id": "movie-1",
                            "Name": "Movie 1",
                            "Overview": "Summary",
                            "RunTimeTicks": 54000000000,
                            "ProductionYear": 2024,
                            "CommunityRating": 8.5,
                            "Type": "Movie",
                        }
                    ]
                }
            )
        return _ok({"Items": []})

    _, _, library = _build(handler, library_ids={"movies": ["lib-m"]})

    deck = await library.fetch_deck(media_types=["movie"])

    assert len(deck) == 1
    card = deck[0]
    assert card["id"] == "movie-1"
    assert card["title"] == "Movie 1"
    assert card["media_type"] == "movie"
    assert card["duration"] == "1h 30m"
    assert card["rating"] == 8.5


@pytest.mark.anyio
async def test_fetch_deck_with_empty_items():
    """fetch_deck returns an empty list when no items match."""

    def handler(request):
        return _ok({"Items": []})

    _, _, library = _build(handler, library_ids={"movies": ["lib-m"]})

    deck = await library.fetch_deck(media_types=["movie"])
    assert deck == []


# ---- resolve_item_for_tmdb ----


@pytest.mark.anyio
async def test_resolve_item_for_tmdb_success():
    """resolve_item_for_tmdb returns title and year."""

    def handler(request):
        if request.url.path == "/Items/movie-123":
            return _ok(
                {
                    "Name": "The Matrix",
                    "OriginalTitle": "The Matrix",
                    "ProductionYear": 1999,
                }
            )
        return _ok({"Items": []})

    _, _, library = _build(handler)

    result = await library.resolve_item_for_tmdb("movie-123")

    assert isinstance(result, SimpleNamespace)
    assert result.title == "The Matrix"
    assert result.year == 1999


@pytest.mark.anyio
async def test_resolve_item_for_tmdb_fallback_to_user_endpoint():
    """resolve_item_for_tmdb falls back to the user-scoped endpoint on global failure."""
    calls = []

    def handler(request):
        path = request.url.path
        calls.append(path)
        if path == "/Items/movie-123":
            return httpx.Response(400)
        if path == "/Users/user-123/Items/movie-123":
            return _ok(
                {
                    "Name": "Fallback Movie",
                    "OriginalTitle": "Fallback Movie",
                    "ProductionYear": 2001,
                }
            )
        return _ok({"Items": []})

    _, _, library = _build(handler)

    result = await library.resolve_item_for_tmdb("movie-123")

    assert result.title == "Fallback Movie"
    assert result.year == 2001
    assert calls.count("/Users/user-123/Items/movie-123") == 1


# ---- fetch_library_image ----


@pytest.mark.anyio
async def test_fetch_library_image_invalid_path_raises_permission():
    """An invalid image path raises PermissionError."""

    def handler(request):
        return _ok({})

    _, _, library = _build(handler)

    with pytest.raises(PermissionError):
        await library.fetch_library_image("bad/path")


@pytest.mark.anyio
async def test_fetch_library_image_403_forbidden():
    """A 403 image response maps to PermissionError."""

    def handler(request):
        return httpx.Response(403)

    _, _, library = _build(handler, library_ids={"movies": ["lib-m"]})

    with pytest.raises(PermissionError):
        await library.fetch_library_image(
            "jellyfin/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4/Primary"
        )


@pytest.mark.anyio
async def test_fetch_library_image_404_not_found():
    """A 404 image response maps to FileNotFoundError."""

    def handler(request):
        return httpx.Response(404)

    _, _, library = _build(handler)

    with pytest.raises(FileNotFoundError):
        await library.fetch_library_image(
            "jellyfin/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4/Primary"
        )


@pytest.mark.anyio
async def test_fetch_library_image_returns_bytes_and_content_type():
    """On success, fetch_library_image returns body bytes and content type."""

    def handler(request):
        return httpx.Response(
            200, content=b"\x89PNG\r\n", headers={"Content-Type": "image/png"}
        )

    _, _, library = _build(handler)

    body, ctype = await library.fetch_library_image(
        "jellyfin/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4/Primary"
    )
    assert body == b"\x89PNG\r\n"
    assert ctype == "image/png"


# ---- api() error handling ----


@pytest.mark.anyio
async def test_api_non_json_response_raises():
    """A 200 response with a non-JSON body raises RuntimeError."""

    def handler(request):
        return httpx.Response(200, content=b"<html>not json</html>")

    _, vault, _ = _build(handler, token="test-token", user_id=None)

    with pytest.raises(RuntimeError):
        await vault.api("GET", "/System/Info")


@pytest.mark.anyio
async def test_api_http_error_raises():
    """A non-2xx response (without retry path) raises RuntimeError."""

    def handler(request):
        return httpx.Response(503)

    _, vault, _ = _build(handler, token="test-token", user_id=None)

    with pytest.raises(RuntimeError):
        await vault.api("GET", "/System/Info", retry=False)
