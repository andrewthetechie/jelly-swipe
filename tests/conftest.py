import pytest
import os

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
    from unittest.mock import patch
    mock_load_dotenv = patch('dotenv.load_dotenv', side_effect=lambda *args, **kwargs: None)
    mock_load_dotenv.start()

    # Monkeypatch Flask() to prevent app initialization
    # Tests import jellyswipe.db and jellyfin_library directly without needing Flask app
    # Return mock object with required attributes/methods to satisfy __init__.py
    class MockApp:
        wsgi_app = type('MockWsgiApp', (), {})()
        secret_key = None

        @staticmethod
        def route(path, **kwargs):
            def decorator(f):
                return f
            return decorator

    mock_flask = patch('flask.Flask', side_effect=lambda *args, **kwargs: MockApp())
    mock_flask.start()

    # Yield control to tests - they can now import jellyswipe modules safely
    yield

    # Cleanup: stop all mocks
    mock_load_dotenv.stop()
    mock_flask.stop()

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
