"""Tests for JellyfinLibraryProvider authentication and user ID resolution."""

from types import SimpleNamespace

import pytest
import requests

from jellyswipe.jellyfin_library import JellyfinLibraryProvider


# ---- Authentication Tests ----

def test_auth_with_api_key(mocker, monkeypatch):
    """Test authentication with API key sets token directly without HTTP call."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request to verify it's NOT called
    mock_session = mocker.MagicMock()
    mock_request = mocker.MagicMock()
    mock_session.request.return_value = mock_request
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and authenticate
    provider = JellyfinLibraryProvider("http://test.local")
    provider.ensure_authenticated()

    # Verify token is set from env var
    assert provider._access_token == "test-api-key"

    # Verify Session.request was NOT called (bypasses _login_from_env)
    mock_request.assert_not_called()


def test_auth_with_username_password_success(mocker, monkeypatch):
    """Test authentication with username/password makes API call and extracts token."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_USERNAME", "testuser")
    monkeypatch.setenv("JELLYFIN_PASSWORD", "testpass")
    monkeypatch.setenv("JELLYFIN_API_KEY", "")  # Clear API key to force username/password

    # Mock Session.request to return successful auth response
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"AccessToken": "user-token-123"}
    mock_session = mocker.MagicMock()
    mock_session.post.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and authenticate
    provider = JellyfinLibraryProvider("http://test.local")
    provider.ensure_authenticated()

    # Verify POST to auth endpoint was called
    mock_session.post.assert_called_once()
    call_args = mock_session.post.call_args
    url = call_args[0][0] if call_args[0] else call_args[1].get('url', '')
    assert "AuthenticateByName" in url
    assert call_args[1]['json']['Username'] == "testuser"
    assert call_args[1]['json']['Pw'] == "testpass"

    # Verify token is extracted
    assert provider._access_token == "user-token-123"


def test_auth_with_username_password_network_error(mocker, monkeypatch):
    """Test authentication with network error raises RuntimeError."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_USERNAME", "testuser")
    monkeypatch.setenv("JELLYFIN_PASSWORD", "testpass")
    monkeypatch.setenv("JELLYFIN_API_KEY", "")

    # Mock Session.request to raise network exception
    mock_session = mocker.MagicMock()
    mock_session.post.side_effect = requests.RequestException("Network error")
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and attempt authentication
    provider = JellyfinLibraryProvider("http://test.local")

    # Verify RuntimeError is raised
    with pytest.raises(RuntimeError, match="Jellyfin authentication failed \\(network error\\)"):
        provider.ensure_authenticated()


def test_auth_with_invalid_credentials(mocker, monkeypatch):
    """Test authentication with invalid credentials raises RuntimeError."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_USERNAME", "testuser")
    monkeypatch.setenv("JELLYFIN_PASSWORD", "wrongpass")
    monkeypatch.setenv("JELLYFIN_API_KEY", "")

    # Mock Session.request to return 401
    mock_response = mocker.MagicMock()
    mock_response.ok = False
    mock_response.status_code = 401
    mock_session = mocker.MagicMock()
    mock_session.post.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and attempt authentication
    provider = JellyfinLibraryProvider("http://test.local")

    # Verify RuntimeError is raised
    with pytest.raises(RuntimeError, match="Jellyfin authentication failed \\(check username, password, or server URL\\)"):
        provider.ensure_authenticated()


def test_auth_with_missing_token_in_response(mocker, monkeypatch):
    """Test authentication when response lacks AccessToken raises RuntimeError."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_USERNAME", "testuser")
    monkeypatch.setenv("JELLYFIN_PASSWORD", "testpass")
    monkeypatch.setenv("JELLYFIN_API_KEY", "")

    # Mock Session.request to return 200 OK but without AccessToken
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"User": {"Id": "user-123"}}  # Missing AccessToken
    mock_session = mocker.MagicMock()
    mock_session.post.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and attempt authentication
    provider = JellyfinLibraryProvider("http://test.local")

    # Verify RuntimeError is raised
    with pytest.raises(RuntimeError, match="Jellyfin authentication failed \\(no access token in response\\)"):
        provider.ensure_authenticated()


# ---- User ID Resolution Tests ----

def test_401_triggers_reset_and_retry(mocker, monkeypatch):
    """Test that 401 response triggers reset and retry logic."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Create mock responses
    mock_response_401 = mocker.MagicMock()
    mock_response_401.status_code = 401

    mock_response_200 = mocker.MagicMock()
    mock_response_200.ok = True
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"Items": []}

    # Track if reset was called
    reset_called = []

    # Mock Session to track behavior
    mock_session = mocker.MagicMock()
    mock_session.get.return_value = mock_response_200
    mock_session.request.side_effect = [mock_response_401, mock_response_200]

    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "old-token"

    # Patch reset to track calls
    original_reset = provider.reset
    def tracked_reset():
        reset_called.append(True)
        # Clear the token to simulate what reset() does
        provider._access_token = None
        original_reset()
    provider.reset = tracked_reset

    # Call _api which should trigger reset and retry
    result = provider._api("GET", "/Items")

    # Verify reset was called
    assert len(reset_called) == 1, "reset() should be called once"

    # Verify token was refreshed from API key
    assert provider._access_token == "test-api-key"


def test_token_caching_prevents_redundant_auth(mocker, monkeypatch):
    """Test that cached token prevents redundant authentication calls."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request
    mock_session = mocker.MagicMock()
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"Items": []}
    mock_session.request.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider
    provider = JellyfinLibraryProvider("http://test.local")

    # Call ensure_authenticated twice
    provider.ensure_authenticated()
    token = provider._access_token
    provider.ensure_authenticated()

    # Verify token remains the same (cached)
    assert provider._access_token == token == "test-api-key"


def test_user_id_from_users_me_endpoint(mocker, monkeypatch):
    """Test user ID resolution from /Users/Me endpoint."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request for /Users/Me
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"Id": "user-123"}
    mock_session = mocker.MagicMock()
    mock_session.request.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set access token
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"

    # Call _user_id
    user_id = provider._user_id()

    # Verify user ID is cached and returned
    assert user_id == "user-123"
    assert provider._cached_user_id == "user-123"

    # Verify second call uses cache
    user_id2 = provider._user_id()
    assert user_id2 == "user-123"
    assert mock_session.request.call_count == 1  # Only one HTTP call


def test_user_id_fallback_to_users_list(mocker, monkeypatch):
    """Test user ID resolution falls back to /Users when /Users/Me fails."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")
    monkeypatch.setenv("JELLYFIN_USERNAME", "testuser")

    # Create mock session
    mock_session = mocker.MagicMock()

    # Mock _api() to fail (simulating /Users/Me failure)
    def mock_api_fail(method, path, **kwargs):
        raise RuntimeError("API call failed")

    # Mock direct .get() call for /Users endpoint
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"Id": "user-456", "Name": "testuser"},
        {"Id": "user-789", "Name": "otheruser"}
    ]
    mock_session.get.return_value = mock_response

    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set access token
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"

    # Patch _api to fail for /Users/Me
    original_api = provider._api
    def patched_api(method, path, **kwargs):
        if path == "/Users/Me":
            raise RuntimeError("API call failed")
        return original_api(method, path, **kwargs)
    provider._api = patched_api

    # Call _user_id
    user_id = provider._user_id()

    # Verify user matching JELLYFIN_USERNAME is selected
    assert user_id == "user-456"
    assert provider._cached_user_id == "user-456"


def test_user_id_fallback_to_first_user(mocker, monkeypatch):
    """Test user ID resolution falls back to first user when no name match."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")
    # No JELLYFIN_USERNAME set

    # Create mock session
    mock_session = mocker.MagicMock()

    # Mock direct .get() call for /Users endpoint
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"Id": "user-999", "Name": "someuser"},
        {"Id": "user-888", "Name": "anotheruser"}
    ]
    mock_session.get.return_value = mock_response

    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set access token
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"

    # Patch _api to fail for /Users/Me
    original_api = provider._api
    def patched_api(method, path, **kwargs):
        if path == "/Users/Me":
            raise RuntimeError("API call failed")
        return original_api(method, path, **kwargs)
    provider._api = patched_api

    # Call _user_id
    user_id = provider._user_id()

    # Verify first user in list is selected
    assert user_id == "user-999"
    assert provider._cached_user_id == "user-999"


# ---- Library Discovery Tests ----

def test_movies_library_id_finds_movies_collection(mocker, monkeypatch):
    """Test that _movies_library_id finds the movies collection type."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request to return library list with movies collection
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Items": [
            {"Id": "lib-123", "CollectionType": "movies", "Name": "Movies"},
            {"Id": "lib-tv", "CollectionType": "tvshows", "Name": "TV Shows"}
        ]
    }
    mock_session = mocker.MagicMock()
    mock_session.request.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call _movies_library_id
    lib_id = provider._movies_library_id()

    # Verify correct library ID is returned and cached
    assert lib_id == "lib-123"
    assert provider._cached_library_ids == {"movies": ["lib-123"]}

    # Verify GET /Users/{uid}/Views was called
    mock_session.request.assert_called_once()
    call_args = mock_session.request.call_args
    assert call_args[0][0] == "GET"
    assert "/Users/user-123/Views" in call_args[0][1]


def test_movies_library_id_raises_when_no_movies_collection(mocker, monkeypatch):
    """Test that _movies_library_id raises RuntimeError when no movies collection exists."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request to return library list without movies
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Items": [
            {"Id": "lib-tv", "CollectionType": "tvshows", "Name": "TV Shows"}
        ]
    }
    mock_session = mocker.MagicMock()
    mock_session.request.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Verify RuntimeError is raised
    with pytest.raises(RuntimeError, match="Jellyfin: no library with CollectionType=movies"):
        provider._movies_library_id()


def test_list_genres_from_items_filters(mocker, monkeypatch):
    """Test that list_genres fetches genres from /Items/Filters endpoint."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request to return genre filters
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "GenreFilters": [
            {"Name": "Action"},
            {"Name": "Science Fiction"},
            {"Name": "Drama"}
        ]
    }
    mock_session = mocker.MagicMock()
    mock_session.request.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state with pre-populated library cache
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"
    provider._cached_library_ids = {"movies": ["lib-123"], "tvshows": []}

    # Call list_genres
    genres = provider.list_genres()

    # Verify genres are returned with "Science Fiction" mapped to "Sci-Fi"
    assert "Action" in genres
    assert "Sci-Fi" in genres  # Mapped from "Science Fiction"
    assert "Drama" in genres
    assert provider._genre_cache == {"all": genres}

    # Verify GET /Items/Filters was called with correct params
    mock_session.request.assert_called_once()
    call_args = mock_session.request.call_args
    assert call_args[0][0] == "GET"
    assert "/Items/Filters" in call_args[0][1]
    assert call_args[1]['params']['ParentId'] == "lib-123"
    assert call_args[1]['params']['UserId'] == "user-123"
    assert call_args[1]['params']['IncludeItemTypes'] == "Movie"


def test_genre_cache_prevents_redundant_api_calls(mocker, monkeypatch):
    """Test that cached genres prevent redundant API calls."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request (should not be called)
    mock_session = mocker.MagicMock()
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state with cached genres
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"
    provider._cached_library_ids = {"movies": ["lib-123"]}
    provider._genre_cache = {"all": ["Action", "Sci-Fi"]}

    # Call list_genres
    genres = provider.list_genres()

    # Verify cached genres are returned without API call
    assert genres == ["Action", "Sci-Fi"]
    mock_session.request.assert_not_called()


def test_list_genres_fallback_to_genres_endpoint(mocker, monkeypatch):
    """Test that list_genres falls back to /Genres when /Items/Filters fails."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - first for movie library discovery, second for TV library discovery,
    # third for empty filters, fourth for genres fallback
    mock_lib_response = mocker.MagicMock()
    mock_lib_response.ok = True
    mock_lib_response.status_code = 200
    mock_lib_response.json.return_value = {
        "Items": [
            {"Id": "lib-123", "CollectionType": "movies", "Name": "Movies"}
        ]
    }
    
    mock_tv_lib_response = mocker.MagicMock()
    mock_tv_lib_response.ok = True
    mock_tv_lib_response.status_code = 200
    mock_tv_lib_response.json.return_value = {
        "Items": []  # No TV libraries
    }
    
    mock_response_empty = mocker.MagicMock()
    mock_response_empty.ok = True
    mock_response_empty.status_code = 200
    mock_response_empty.json.return_value = {"GenreFilters": []}

    mock_response_genres = mocker.MagicMock()
    mock_response_genres.ok = True
    mock_response_genres.status_code = 200
    mock_response_genres.json.return_value = {
        "Items": [
            {"Name": "Comedy"},
            {"Name": "Horror"}
        ]
    }

    mock_session = mocker.MagicMock()
    mock_session.request.side_effect = [
        mock_lib_response, mock_tv_lib_response, mock_response_empty, mock_response_genres
    ]
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call list_genres
    genres = provider.list_genres()

    # Verify both endpoints were called and genres are returned
    assert "Comedy" in genres
    assert "Horror" in genres
    assert mock_session.request.call_count == 4  # Views x2, /Items/Filters, /Genres


# ---- Deck Fetching Tests ----

def test_fetch_deck_all_movies(mocker, monkeypatch):
    """Test that fetch_deck returns all movies with correct card format."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - first for library discovery, second for items
    mock_lib_response = mocker.MagicMock()
    mock_lib_response.ok = True
    mock_lib_response.status_code = 200
    mock_lib_response.json.return_value = {
        "Items": [
            {"Id": "lib-123", "CollectionType": "movies", "Name": "Movies"}
        ]
    }
    
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Items": [
            {
                "Id": "movie-1",
                "Name": "Movie 1",
                "Overview": "Summary 1",
                "RunTimeTicks": 54000000000,  # 1h 30m (90 minutes = 5400 seconds)
                "ProductionYear": 2024,
                "CommunityRating": 8.5
            }
        ]
    }
    mock_session = mocker.MagicMock()
    mock_session.request.side_effect = [mock_lib_response, mock_response]
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call fetch_deck
    deck = provider.fetch_deck(media_types=["movie"])

    # Verify deck contains one card with correct format
    assert len(deck) == 1
    card = deck[0]
    assert card["id"] == "movie-1"
    assert card["title"] == "Movie 1"
    assert card["summary"] == "Summary 1"
    assert card["rating"] == 8.5
    assert card["duration"] == "1h 30m"
    assert card["year"] == 2024
    assert card["thumb"] == "/proxy?path=jellyfin/movie-1/Primary"
    assert card["media_type"] == "movie"

    # Verify GET /Items was called with correct params
    assert mock_session.request.call_count == 2
    call_args = mock_session.request.call_args_list[1]
    assert call_args[0][0] == "GET"
    assert "/Items" in call_args[0][1]
    assert call_args[1]['params']['ParentId'] == "lib-123"
    assert call_args[1]['params']['UserId'] == "user-123"
    assert call_args[1]['params']['IncludeItemTypes'] == "Movie"
    assert call_args[1]['params']['Recursive'] == "true"
    assert call_args[1]['params']['SortBy'] == "Random"
    assert call_args[1]['params']['Limit'] == 150


def test_fetch_deck_with_genre_filter(mocker, monkeypatch):
    """Test that fetch_deck with genre filter uses correct API params."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - first for library discovery, second for items
    mock_lib_response = mocker.MagicMock()
    mock_lib_response.ok = True
    mock_lib_response.status_code = 200
    mock_lib_response.json.return_value = {
        "Items": [
            {"Id": "lib-123", "CollectionType": "movies", "Name": "Movies"}
        ]
    }
    
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Items": [
            {
                "Id": "movie-2",
                "Name": "Sci-Fi Movie",
                "Overview": "",
                "RunTimeTicks": 0,
                "ProductionYear": 2023
            }
        ]
    }
    mock_session = mocker.MagicMock()
    mock_session.request.side_effect = [mock_lib_response, mock_response]
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call fetch_deck with genre filter
    deck = provider.fetch_deck(media_types=["movie"], genre_name="Sci-Fi")

    # Verify "Sci-Fi" was mapped to "Science Fiction" in API call
    call_args = mock_session.request.call_args_list[1]
    assert call_args[1]['params']['Genres'] == "Science Fiction"
    assert call_args[1]['params']['Limit'] == 100
    assert call_args[1]['params']['SortBy'] == "Random"


def test_fetch_deck_recently_added_sort(mocker, monkeypatch):
    """Test that fetch_deck with 'Recently Added' uses DateCreated descending sort."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - first for library discovery, second for items
    mock_lib_response = mocker.MagicMock()
    mock_lib_response.ok = True
    mock_lib_response.status_code = 200
    mock_lib_response.json.return_value = {
        "Items": [
            {"Id": "lib-123", "CollectionType": "movies", "Name": "Movies"}
        ]
    }
    
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"Items": []}
    mock_session = mocker.MagicMock()
    mock_session.request.side_effect = [mock_lib_response, mock_response]
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call fetch_deck with "Recently Added"
    deck = provider.fetch_deck(media_types=["movie"], genre_name="Recently Added")

    # Verify DateCreated descending sort is used
    call_args = mock_session.request.call_args_list[1]
    assert call_args[1]['params']['SortBy'] == "DateCreated"
    assert call_args[1]['params']['SortOrder'] == "Descending"
    assert call_args[1]['params']['Limit'] == 100


# ---- Transformation Tests ----

def test_item_to_card_transformation(mocker, monkeypatch):
    """Test that _item_to_card extracts all 7 fields correctly."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Create provider
    provider = JellyfinLibraryProvider("http://test.local")

    # Create test item with all fields
    item = {
        "Id": "movie-123",
        "Name": "Test Movie",
        "Overview": "Test summary",
        "RunTimeTicks": 81000000000,  # 2h 15m (135 minutes = 8100 seconds)
        "ProductionYear": 2024,
        "CommunityRating": 9.0,
        "CriticRating": 8.5
    }

    # Transform item to card
    card = provider._item_to_card(item)

    # Verify all 7 fields are extracted correctly
    assert card["id"] == "movie-123"
    assert card["title"] == "Test Movie"
    assert card["summary"] == "Test summary"
    assert card["rating"] == 9.0  # CommunityRating takes precedence
    assert card["duration"] == "2h 15m"
    assert card["year"] == 2024
    assert card["thumb"] == "/proxy?path=jellyfin/movie-123/Primary"

    # Test with missing CommunityRating (should fall back to CriticRating)
    item2 = {
        "Id": "movie-456",
        "Name": "Movie 2",
        "Overview": "",
        "RunTimeTicks": 27000000000,  # 45m (45 minutes = 2700 seconds)
        "ProductionYear": 2023,
        "CriticRating": 7.5
    }
    card2 = provider._item_to_card(item2)
    assert card2["rating"] == 7.5
    assert card2["duration"] == "45m"

    # Test with empty runtime
    item3 = {
        "Id": "movie-789",
        "Name": "Movie 3",
        "Overview": "",
        "RunTimeTicks": 0,
        "ProductionYear": 2022
    }
    card3 = provider._item_to_card(item3)
    assert card3["duration"] == ""


def test_resolve_item_for_tmdb_success(mocker, monkeypatch):
    """Test that resolve_item_for_tmdb returns title and year."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request to return item details
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Id": "movie-123",
        "Name": "Test Movie",
        "OriginalTitle": "Original Name",
        "ProductionYear": 2024
    }
    mock_session = mocker.MagicMock()
    mock_session.request.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Resolve item for TMDB
    result = provider.resolve_item_for_tmdb("movie-123")

    # Verify title and year are returned
    assert isinstance(result, SimpleNamespace)
    assert result.title == "Test Movie"  # Name takes precedence
    assert result.year == 2024

    # Verify GET /Items/{id} was called
    call_args = mock_session.request.call_args
    assert call_args[0][0] == "GET"
    assert "/Items/movie-123" in call_args[0][1]
    assert call_args[1]['params']['Fields'] == "Name,OriginalTitle,ProductionYear"


def test_resolve_item_for_tmdb_fallback_to_user_endpoint(mocker, monkeypatch):
    """Test that resolve_item_for_tmdb falls back to user-scoped endpoint."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - first call fails, second succeeds
    mock_response_200 = mocker.MagicMock()
    mock_response_200.ok = True
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {
        "Id": "movie-123",
        "Name": "Test Movie",
        "ProductionYear": 2024
    }

    mock_session = mocker.MagicMock()
    # First call to /Items/movie-123 raises RuntimeError
    # Second call to /Users/{uid}/Items/movie-123 succeeds
    call_count = [0]
    def mock_request(method, url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("Global lookup failed")
        return mock_response_200
    mock_session.request.side_effect = mock_request
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Resolve item for TMDB
    result = provider.resolve_item_for_tmdb("movie-123")

    # Verify both endpoints were attempted
    assert call_count[0] == 2
    assert result.title == "Test Movie"
    assert result.year == 2024


# ---- Error & Edge Case Tests ----

def test_fetch_deck_with_empty_items(mocker, monkeypatch):
    """Test that fetch_deck returns empty list when Items array is empty."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - first for library discovery, second for empty items
    mock_lib_response = mocker.MagicMock()
    mock_lib_response.ok = True
    mock_lib_response.status_code = 200
    mock_lib_response.json.return_value = {
        "Items": [
            {"Id": "lib-123", "CollectionType": "movies", "Name": "Movies"}
        ]
    }
    
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"Items": []}
    mock_session = mocker.MagicMock()
    mock_session.request.side_effect = [mock_lib_response, mock_response]
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call fetch_deck
    deck = provider.fetch_deck(media_types=["movie"])

    # Verify empty list is returned (not None)
    assert deck == []
    assert isinstance(deck, list)


def test_fetch_deck_with_missing_item_fields(mocker, monkeypatch):
    """Test that fetch_deck handles missing fields with defaults."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - first for library discovery, second for items
    mock_lib_response = mocker.MagicMock()
    mock_lib_response.ok = True
    mock_lib_response.status_code = 200
    mock_lib_response.json.return_value = {
        "Items": [
            {"Id": "lib-123", "CollectionType": "movies", "Name": "Movies"}
        ]
    }
    
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Items": [
            {"Id": "movie-1"}  # Missing Name, Overview, etc.
        ]
    }
    mock_session = mocker.MagicMock()
    mock_session.request.side_effect = [mock_lib_response, mock_response]
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call fetch_deck
    deck = provider.fetch_deck(media_types=["movie"])

    # Verify card uses defaults for missing fields
    assert len(deck) == 1
    card = deck[0]
    assert card["id"] == "movie-1"
    assert card["title"] == ""  # Default for missing string
    assert card["summary"] == ""  # Default for missing string
    assert card["rating"] is None  # Default for missing numeric
    assert card["year"] is None  # Default for missing numeric
    assert card["media_type"] == "movie"


def test_fetch_library_image_403_forbidden(mocker, monkeypatch):
    """Test that fetch_library_image raises PermissionError for 403."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request to return 403
    mock_response = mocker.MagicMock()
    mock_response.ok = False
    mock_response.status_code = 403
    mock_session = mocker.MagicMock()
    mock_session.get.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"

    # Verify PermissionError is raised (using valid UUID format)
    with pytest.raises(PermissionError, match="Jellyfin image forbidden"):
        provider.fetch_library_image("jellyfin/1234567890abcdef1234567890abcdef/Primary")


def test_fetch_library_image_404_not_found(mocker, monkeypatch):
    """Test that fetch_library_image raises FileNotFoundError for 404."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request to return 404
    mock_response = mocker.MagicMock()
    mock_response.ok = False
    mock_response.status_code = 404
    mock_session = mocker.MagicMock()
    mock_session.get.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"

    # Verify FileNotFoundError is raised (using valid UUID format)
    with pytest.raises(FileNotFoundError, match="Jellyfin image not found"):
        provider.fetch_library_image("jellyfin/1234567890abcdef1234567890abcdef/Primary")


def test_fetch_library_image_invalid_path(mocker, monkeypatch):
    """Test that fetch_library_image raises PermissionError for invalid path."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Create provider
    provider = JellyfinLibraryProvider("http://test.local")

    # Verify PermissionError is raised for invalid path
    with pytest.raises(PermissionError, match="Invalid Jellyfin image path"):
        provider.fetch_library_image("invalid/path")


def test_authenticate_user_session_missing_credentials(mocker, monkeypatch):
    """Test that authenticate_user_session raises RuntimeError for empty credentials."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Create provider
    provider = JellyfinLibraryProvider("http://test.local")

    # Verify RuntimeError is raised for empty username/password
    with pytest.raises(RuntimeError, match="Jellyfin login failed \\(missing username/password\\)"):
        provider.authenticate_user_session("", "")


def test_authenticate_user_session_missing_token_or_user_id(mocker, monkeypatch):
    """Test that authenticate_user_session raises RuntimeError when response lacks token or user_id."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request to return response with AccessToken but missing User.Id
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"AccessToken": "token-123"}  # Missing User.Id
    mock_session = mocker.MagicMock()
    mock_session.post.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider
    provider = JellyfinLibraryProvider("http://test.local")

    # Verify RuntimeError is raised
    with pytest.raises(RuntimeError, match="Jellyfin login failed \\(missing token or user id\\)"):
        provider.authenticate_user_session("user", "pass")


def test_api_non_json_response(mocker, monkeypatch):
    """Test that _api raises RuntimeError for non-JSON response."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request to return 200 OK but with invalid JSON
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_session = mocker.MagicMock()
    mock_session.request.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"

    # Verify RuntimeError is raised
    with pytest.raises(RuntimeError, match="Jellyfin returned non-JSON body"):
        provider._api("GET", "/Items")


# ---- TV Show Tests ----

def test_series_to_card_transformation(mocker, monkeypatch):
    """Test that _series_to_card extracts TV show fields correctly."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Create provider
    provider = JellyfinLibraryProvider("http://test.local")

    # Create test series item with all fields
    series = {
        "Id": "series-123",
        "Name": "Test Series",
        "Overview": "Test series summary",
        "ProductionYear": 2024,
        "ChildCount": 3,  # 3 seasons
        "Type": "Series",
    }

    # Transform series to card
    card = provider._series_to_card(series)

    # Verify all TV show fields are extracted correctly
    assert card["id"] == "series-123"
    assert card["title"] == "Test Series"
    assert card["summary"] == "Test series summary"
    assert card["year"] == 2024
    assert card["media_type"] == "tv_show"
    assert card["season_count"] == 3
    # TV cards should NOT have duration or rating
    assert "duration" not in card
    assert "rating" not in card

    # Test with missing ChildCount
    series2 = {
        "Id": "series-456",
        "Name": "Series 2",
        "Overview": "",
        "ProductionYear": 2023,
    }
    card2 = provider._series_to_card(series2)
    assert card2["season_count"] is None


def test_fetch_deck_tv_shows_only(mocker, monkeypatch):
    """Test that fetch_deck with tv_show returns only TV series cards."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - first for library discovery, second for TV items
    mock_lib_response = mocker.MagicMock()
    mock_lib_response.ok = True
    mock_lib_response.status_code = 200
    mock_lib_response.json.return_value = {
        "Items": [
            {"Id": "lib-tv", "CollectionType": "tvshows", "Name": "TV Shows"}
        ]
    }
    
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Items": [
            {
                "Id": "series-1",
                "Name": "TV Series 1",
                "Overview": "Series summary 1",
                "ProductionYear": 2024,
                "ChildCount": 2,
                "Type": "Series",
            }
        ]
    }
    mock_session = mocker.MagicMock()
    mock_session.request.side_effect = [mock_lib_response, mock_response]
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call fetch_deck for TV shows only
    deck = provider.fetch_deck(media_types=["tv_show"])

    # Verify deck contains one TV card with correct format
    assert len(deck) == 1
    card = deck[0]
    assert card["id"] == "series-1"
    assert card["title"] == "TV Series 1"
    assert card["summary"] == "Series summary 1"
    assert card["year"] == 2024
    assert card["season_count"] == 2
    assert card["media_type"] == "tv_show"
    # TV cards should NOT have duration
    assert "duration" not in card

    # Verify GET /Items was called with Series item type
    assert mock_session.request.call_count == 2
    call_args = mock_session.request.call_args_list[1]
    assert call_args[1]['params']['IncludeItemTypes'] == "Series"


def test_fetch_deck_mixed_media_types(mocker, monkeypatch):
    """Test that fetch_deck with both movie and tv_show returns mixed cards."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Create mock session
    mock_session = mocker.MagicMock()
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"
    # Pre-populate library cache to avoid library discovery calls
    provider._cached_library_ids = {
        "movies": ["lib-movies"],
        "tvshows": ["lib-tv"],
    }

    # Configure mock responses for /Items queries
    def request_side_effect(method, url, **kwargs):
        mock_response = mocker.MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        
        # Check if this is a movie or TV query based on IncludeItemTypes param
        params = kwargs.get('params', {})
        if params.get('IncludeItemTypes') == 'Movie':
            mock_response.json.return_value = {
                "Items": [
                    {
                        "Id": "movie-1",
                        "Name": "Movie 1",
                        "Overview": "Movie summary",
                        "RunTimeTicks": 54000000000,
                        "ProductionYear": 2024,
                        "CommunityRating": 8.5,
                        "Type": "Movie",
                    }
                ]
            }
        elif params.get('IncludeItemTypes') == 'Series':
            mock_response.json.return_value = {
                "Items": [
                    {
                        "Id": "series-1",
                        "Name": "TV Series 1",
                        "Overview": "Series summary",
                        "ProductionYear": 2023,
                        "ChildCount": 3,
                        "Type": "Series",
                    }
                ]
            }
        else:
            mock_response.json.return_value = {"Items": []}
        
        return mock_response
    
    mock_session.request.side_effect = request_side_effect

    # Call fetch_deck for both media types
    deck = provider.fetch_deck(media_types=["movie", "tv_show"])

    # Verify deck contains both movie and TV cards
    assert len(deck) == 2
    
    # Find movie and TV cards
    movie_card = next(c for c in deck if c["media_type"] == "movie")
    tv_card = next(c for c in deck if c["media_type"] == "tv_show")
    
    # Verify movie card
    assert movie_card["id"] == "movie-1"
    assert movie_card["title"] == "Movie 1"
    assert movie_card["duration"] == "1h 30m"
    assert movie_card["rating"] == 8.5
    
    # Verify TV card
    assert tv_card["id"] == "series-1"
    assert tv_card["title"] == "TV Series 1"
    assert tv_card["season_count"] == 3
    assert "duration" not in tv_card


def test_fetch_deck_tv_show_with_genre_filter(mocker, monkeypatch):
    """Test that fetch_deck with tv_show and genre filter uses correct API params."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - library discovery, TV items
    mock_lib_response = mocker.MagicMock()
    mock_lib_response.ok = True
    mock_lib_response.status_code = 200
    mock_lib_response.json.return_value = {
        "Items": [
            {"Id": "lib-tv", "CollectionType": "tvshows", "Name": "TV Shows"}
        ]
    }
    
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Items": [
            {
                "Id": "series-1",
                "Name": "Drama Series",
                "Overview": "",
                "ProductionYear": 2023,
                "Type": "Series",
            }
        ]
    }
    mock_session = mocker.MagicMock()
    mock_session.request.side_effect = [mock_lib_response, mock_response]
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call fetch_deck with TV shows and genre filter
    deck = provider.fetch_deck(media_types=["tv_show"], genre_name="Drama")

    # Verify genre filter was applied
    call_args = mock_session.request.call_args_list[1]
    assert call_args[1]['params']['Genres'] == "Drama"
    assert call_args[1]['params']['IncludeItemTypes'] == "Series"


def test_fetch_deck_no_tv_library_returns_empty(mocker, monkeypatch):
    """Test that fetch_deck returns empty list when no TV library exists."""
    # Mock environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")

    # Mock Session.request - library discovery shows no TV libraries
    mock_lib_response = mocker.MagicMock()
    mock_lib_response.ok = True
    mock_lib_response.status_code = 200
    mock_lib_response.json.return_value = {
        "Items": [
            {"Id": "lib-movies", "CollectionType": "movies", "Name": "Movies"}
        ]
    }
    
    mock_session = mocker.MagicMock()
    mock_session.request.side_effect = [mock_lib_response]
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"

    # Call fetch_deck for TV shows only (no TV library exists)
    deck = provider.fetch_deck(media_types=["tv_show"])

    # Verify empty list is returned without raising
    assert deck == []
    assert isinstance(deck, list)
    
    # Verify only library discovery was called (no /Items query)
    assert mock_session.request.call_count == 1

