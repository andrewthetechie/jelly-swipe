import os
import secrets
from unittest.mock import MagicMock, patch

import pytest

# Set required environment variables at module level to satisfy jellyswipe/__init__.py
# This must happen before any imports that trigger __init__.py validation
os.environ.setdefault("JELLYFIN_URL", "http://test.jellyfin.local")
os.environ.setdefault("JELLYFIN_API_KEY", "test-api-key")
os.environ.setdefault("TMDB_API_KEY", "test-tmdb-key")
os.environ.setdefault("FLASK_SECRET", "test-secret-key")


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Set up test environment before any tests run.
    This fixture auto-runs for all tests (autouse=True) and runs once per session.

    Per D-04: Monkeypatch load_dotenv() and Flask() to allow framework-agnostic imports.
    """
    # Monkeypatch load_dotenv() to skip .env file loading
    # This prevents loading .env from project root which may not exist or have wrong values
    mock_load_dotenv = patch('dotenv.load_dotenv', side_effect=lambda *args, **kwargs: None)
    mock_load_dotenv.start()

    # Yield control to tests - they can now import jellyswipe modules safely
    yield

    # Cleanup: stop all mocks
    mock_load_dotenv.stop()


@pytest.fixture
def mocker():
    """
    Lightweight pytest-mock compatible fixture for this repository.

    Supports the subset currently used by tests: MagicMock and patch(...).
    """

    class _Mocker:
        MagicMock = MagicMock

        def __init__(self):
            self._patchers = []

        def patch(self, target, *args, **kwargs):
            patcher = patch(target, *args, **kwargs)
            self._patchers.append(patcher)
            return patcher.start()

        def stopall(self):
            while self._patchers:
                self._patchers.pop().stop()

    helper = _Mocker()
    try:
        yield helper
    finally:
        helper.stopall()

@pytest.fixture
def mock_env_vars(monkeypatch):
    """
    Provide test environment variables for individual tests.
    Tests can use this fixture if they need to override env vars per test.

    This is function-scoped (default) to ensure test isolation.
    """
    monkeypatch.setenv("JELLYFIN_URL", "http://test.jellyfin.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")
    monkeypatch.setenv("TMDB_API_KEY", "test-tmdb-key")
    monkeypatch.setenv("FLASK_SECRET", "test-secret-key")
    yield


@pytest.fixture
def db_path(tmp_path):
    """
    Create a temporary database file path for isolated testing.

    This fixture is function-scoped to ensure each test gets its own database.
    tmp_path automatically handles cleanup of the temporary file after the test.

    Per D-01: Use tmp_path fixture for isolated SQLite databases.
    """
    db_file = tmp_path / "test.db"
    yield str(db_file)


@pytest.fixture
def db_connection(db_path, monkeypatch):
    """
    Provide a database connection with fresh schema for each test.

    This fixture:
    1. Patches jellyswipe.db.DB_PATH to use the temporary database file
    2. Initializes the database schema by calling init_db()
    3. Yields a database connection to the test
    4. Closes the connection after the test

    Per D-03: Use monkeypatch to set DB_PATH global variable.
    Per D-06: Each test receives a fresh database with init_db() already called.

    The function scope ensures complete test isolation - no state leaks between tests.
    """
    import jellyswipe.db

    # Patch the global DB_PATH to use the temporary database file
    monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

    # Initialize the database schema
    jellyswipe.db.init_db()

    # Get a database connection and yield it to the test
    conn = jellyswipe.db.get_db()
    try:
        yield conn
    finally:
        # Ensure the connection is closed after the test
        conn.close()


class FakeProvider:
    """General-purpose provider mock for route testing.

    Covers all JellyfinLibraryProvider methods used by routes.
    Individual tests can override specific methods or replace the
    entire mock via monkeypatch for specific behavior (D-06).
    """

    def __init__(self, user_id="verified-user", token="valid-token"):
        self._user_id = user_id
        self._token = token
        self.favorites_added = []

    def server_primary_user_id_for_delegate(self):
        return self._user_id

    def server_access_token_for_delegate(self):
        return self._token

    def extract_media_browser_token(self, auth_header):
        marker = 'Token="'
        if marker in auth_header and auth_header.endswith('"'):
            return auth_header.split(marker, 1)[1][:-1]
        return ""

    def resolve_user_id_from_token(self, token):
        if token == self._token:
            return self._user_id
        return None

    def add_to_user_favorites(self, user_token, movie_id):
        self.favorites_added.append((user_token, movie_id))

    def fetch_deck(self, genre=None):
        return []

    def list_genres(self):
        return ["All", "Action", "Comedy"]

    def server_info(self):
        return {"server_name": "Test Server"}

    def resolve_item_for_tmdb(self, movie_id):
        raise RuntimeError("item lookup failed")

    def fetch_library_image(self, path):
        return (b"", "image/jpeg")

    def authenticate_user_session(self, username, password):
        return {"token": self._token, "user_id": self._user_id}


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create a fresh Flask app instance for route testing.

    Each test gets its own isolated app with:
    - Temp SQLite database (via tmp_path)
    - TESTING mode enabled (D-10)
    - Unique secret key to prevent session leakage (D-11)
    - FakeProvider mock for provider singleton (D-05)
    - Clean token cache (no stale entries)

    Route tests use the `client` fixture. Direct DB tests continue
    using the existing `db_connection` fixture (D-04).
    """
    import jellyswipe as jellyswipe_module
    from jellyswipe import create_app

    db_file = str(tmp_path / "test_route.db")
    test_config = {
        "DB_PATH": db_file,
        "TESTING": True,
        "SECRET_KEY": secrets.token_hex(16),
    }

    flask_app = create_app(test_config=test_config)

    # Patch provider singleton with FakeProvider (D-05)
    # monkeypatch auto-restores after test
    fake_provider = FakeProvider()
    monkeypatch.setattr(
        jellyswipe_module, "_provider_singleton", fake_provider, raising=False
    )
    jellyswipe_module._token_user_id_cache.clear()

    yield flask_app


@pytest.fixture
def client(app):
    """Provide a Flask test client for HTTP requests.

    Depends on the app fixture for proper isolation.
    """
    return app.test_client()
