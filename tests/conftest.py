import pytest
import os

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

    # Set required environment variables to satisfy jellyswipe/__init__.py validation
    # These are test values only - real API calls will be mocked in test files
    os.environ.setdefault("JELLYFIN_URL", "http://test.jellyfin.local")
    os.environ.setdefault("JELLYFIN_API_KEY", "test-api-key")
    os.environ.setdefault("TMDB_API_KEY", "test-tmdb-key")
    os.environ.setdefault("FLASK_SECRET", "test-secret-key")

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
