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
    assert provider._cached_library_id == "lib-123"

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

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"
    provider._cached_library_id = "lib-123"

    # Call list_genres
    genres = provider.list_genres()

    # Verify genres are returned with "Science Fiction" mapped to "Sci-Fi"
    assert "Action" in genres
    assert "Sci-Fi" in genres  # Mapped from "Science Fiction"
    assert "Drama" in genres
    assert provider._genre_cache == genres

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
    mock_response = mocker.MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"GenreFilters": []}
    mock_session.request.return_value = mock_response
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state with cached genres
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"
    provider._cached_library_id = "lib-123"
    provider._genre_cache = ["Action", "Sci-Fi"]

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

    # Mock Session.request - first call returns empty, second returns genres
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
    mock_session.request.side_effect = [mock_response_empty, mock_response_genres]
    mocker.patch('jellyswipe.jellyfin_library.requests.Session', return_value=mock_session)

    # Create provider and set up state
    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"
    provider._cached_library_id = "lib-123"

    # Call list_genres
    genres = provider.list_genres()

    # Verify both endpoints were called and genres are returned
    assert "Comedy" in genres
    assert "Horror" in genres
    assert mock_session.request.call_count == 2  # /Items/Filters and /Genres

