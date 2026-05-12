import asyncio
import contextlib
import json
import os
import sqlite3
from base64 import b64encode
from unittest.mock import MagicMock, patch

import pytest
import itsdangerous
from fastapi.testclient import TestClient

from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    initialize_runtime,
)
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head

# Set required environment variables at module level to satisfy itsdangerous signing
# and AppConfig construction for tests that check env vars directly.
os.environ.setdefault("JELLYFIN_URL", "http://test.jellyfin.local")
os.environ.setdefault("JELLYFIN_API_KEY", "test-api-key")
os.environ.setdefault("TMDB_ACCESS_TOKEN", "test-tmdb-token")
os.environ.setdefault("FLASK_SECRET", "test-secret-key")
os.environ.setdefault("ALLOW_PRIVATE_JELLYFIN", "1")


def set_session_cookie(client, data: dict, secret_key: str) -> None:
    """Inject session state into a FastAPI TestClient's cookie jar.

    Replicates Starlette 1.0.0 SessionMiddleware signing format exactly:
      base64(json_bytes).timestamp.signature via itsdangerous.TimestampSigner.

    VERIFIED against starlette.middleware.sessions source code.
    Do NOT use URLSafeTimedSerializer — that is Flask's format, not Starlette's.
    """
    signer = itsdangerous.TimestampSigner(str(secret_key))
    payload = b64encode(json.dumps(data).encode("utf-8"))
    signed = signer.sign(payload)
    host = getattr(client.base_url, "host", "")
    domain = f"{host}.local" if host and "." not in host else host
    client.cookies.set("session", signed.decode("utf-8"), domain=domain, path="/")


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
    monkeypatch.setenv("TMDB_ACCESS_TOKEN", "test-tmdb-token")
    monkeypatch.setenv("FLASK_SECRET", "test-secret-key")
    monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
    yield


@contextlib.contextmanager
def sqlite_test_connection(db_path: str):
    """Open sqlite3 directly to the given ``db_path``."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
    finally:
        conn.close()


@contextlib.contextmanager
def sqlite_test_transaction(db_path: str):
    """Like ``get_db_closing``: commit-on-context-exit semantics for XSS/route seeds."""
    with sqlite_test_connection(db_path) as conn:
        with conn:
            yield conn


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


def _bootstrap_temp_db_runtime(db_path):
    """Provision one temp database through Alembic plus the async runtime path."""
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)

    os.environ["DB_PATH"] = db_path

    upgrade_to_head(sync_database_url)
    asyncio.run(initialize_runtime(runtime_database_url))

    return {
        "db_path": db_path,
        "sync_database_url": sync_database_url,
        "runtime_database_url": runtime_database_url,
    }


def _dispose_test_runtime() -> None:
    """Tear down the shared async runtime from sync pytest fixtures."""
    asyncio.run(dispose_runtime())


@pytest.fixture
def db_connection(db_path, monkeypatch):
    """
    Provide a database connection with fresh schema for each test.

    This fixture:
    1. Patches DB_PATH and DATABASE_URL env vars to use the temporary database file
    2. Initializes the database schema by running Alembic upgrade head
    3. Yields a database connection to the test
    4. Closes the connection after the test

    Per D-06: Each test receives a fresh database with Alembic already applied.

    The function scope ensures complete test isolation - no state leaks between tests.
    """
    _bootstrap_temp_db_runtime(db_path)

    try:
        with sqlite_test_connection(db_path) as conn:
            yield conn
    finally:
        _dispose_test_runtime()


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

    def fetch_deck(self, media_types=None, genre_name=None, hide_watched=False):
        """Return a list of fake movie/TV cards for deck testing.

        Args:
            media_types: List of media types to fetch ("movie", "tv_show").
                        Defaults to ["movie"] if not specified.
            genre_name: Optional genre filter (ignored in fake implementation).
            hide_watched: Optional boolean to hide watched items (ignored in fake implementation).

        Returns:
            List of card dicts with media_type field set.
        """
        if media_types is None:
            media_types = ["movie"]

        cards = []
        if "movie" in media_types:
            cards.extend(
                [
                    {
                        "id": f"movie-{i}",
                        "title": f"Movie {i}",
                        "summary": f"Summary {i}",
                        "thumb": f"/proxy?path=jellyfin/movie-{i}/Primary",
                        "rating": 7.0,
                        "duration": "1h 30m",
                        "year": 2024,
                        "media_type": "movie",
                    }
                    for i in range(25)
                ]
            )
        if "tv_show" in media_types:
            cards.extend(
                [
                    {
                        "id": f"tv-{i}",
                        "title": f"TV Show {i}",
                        "summary": f"TV Summary {i}",
                        "thumb": f"/proxy?path=jellyfin/tv-{i}/Primary",
                        "year": 2024,
                        "media_type": "tv_show",
                        "season_count": 3,
                    }
                    for i in range(25)
                ]
            )
        return cards

    def list_genres(self):
        return ["All", "Action", "Comedy"]

    def server_info(self):
        return {
            "machineIdentifier": "test-server-id",
            "name": "TestServer",
            "webUrl": "",
        }

    def resolve_item_for_tmdb(self, movie_id):
        from types import SimpleNamespace

        return SimpleNamespace(
            title=f"Movie-{movie_id}",
            year=2026,
            thumb=f"/proxy?path=jellyfin/{movie_id}/Primary",
        )

    def fetch_library_image(self, path):
        return (b"", "image/jpeg")


def _make_test_config(db_path):
    """Construct an AppConfig for testing with explicit values."""
    from jellyswipe.config import AppConfig

    return AppConfig(
        jellyfin_url="http://test",
        jellyfin_api_key="k",
        tmdb_access_token="t",
        flask_secret=os.environ["FLASK_SECRET"],
        db_path=db_path,
    )


@pytest.fixture
def app(db_path, monkeypatch):
    """Create a fresh FastAPI app instance for route testing.

    Each test gets its own isolated app with:
    - Temp SQLite database (via tmp_path)
    - TESTING mode enabled
    - SECRET_KEY matching FLASK_SECRET env var (so set_session_cookie cookies are accepted)
    - dependency_overrides for require_auth (D-01) and get_provider (D-05)
    - Clean rate limiter state

    Teardown clears dependency_overrides to prevent state leakage (D-01 success criterion 3).
    """
    from jellyswipe import create_app
    from jellyswipe.dependencies import require_auth, get_provider, AuthUser, _provider_singleton as _dep_provider
    import jellyswipe.dependencies as deps

    bootstrap = _bootstrap_temp_db_runtime(db_path)
    test_config = _make_test_config(db_path)
    fast_app = create_app(config=test_config)

    # Set provider singleton on dependencies module
    fake_provider = FakeProvider()
    deps._provider_singleton = fake_provider

    # Override auth — no DB vault needed (D-01)
    # Default identity matches FakeProvider's user_id/token (D-03)
    fast_app.dependency_overrides[require_auth] = lambda: AuthUser(
        jf_token="valid-token", user_id="verified-user"
    )

    # Override provider — replaces monkeypatch of _provider_singleton (D-05)
    fast_app.dependency_overrides[get_provider] = lambda: fake_provider

    from jellyswipe.rate_limiter import rate_limiter as _rl

    _rl.reset()

    yield fast_app

    # Dispose the cached runtime before clearing test singletons so the next
    # temp database cannot inherit the previous engine/sessionmaker binding.
    _dispose_test_runtime()
    fast_app.dependency_overrides.clear()  # CRITICAL: prevents override state leakage
    # Clear provider singleton on teardown
    deps._provider_singleton = None


@pytest.fixture
def client(app):
    """Provide a FastAPI TestClient for HTTP requests.

    Depends on the app fixture for proper isolation.
    Cookies persist between calls within the same client instance.
    Uses context manager to ensure lifespan startup/shutdown events are triggered.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def app_real_auth(db_path, monkeypatch):
    """FastAPI app with real require_auth — for auth integration tests only.

    Does NOT set dependency_overrides[require_auth]. Auth goes through
    real require_auth -> auth.get_current_token() -> DB lookup.
    Used by: test_routes_auth.py and test_route_authorization.py (D-02).

    Uses db_path fixture to align database with db_connection (Plan 03 fix).
    """
    from jellyswipe import create_app
    from jellyswipe.dependencies import get_provider
    import jellyswipe.dependencies as deps

    bootstrap = _bootstrap_temp_db_runtime(db_path)

    # Set provider singleton BEFORE creating app
    fake_provider = FakeProvider()
    deps._provider_singleton = fake_provider

    test_config = _make_test_config(db_path)
    fast_app = create_app(config=test_config)
    # NOTE: NO dependency_overrides[require_auth] — real auth path (D-02)
    fast_app.dependency_overrides[get_provider] = lambda: fake_provider

    from jellyswipe.rate_limiter import rate_limiter as _rl

    _rl.reset()

    yield fast_app
    # Dispose the cached runtime before clearing overrides/singletons so a
    # later fixture can rebind cleanly to another temp SQLite database.
    _dispose_test_runtime()
    fast_app.dependency_overrides.clear()
    # Clear provider singleton on teardown
    deps._provider_singleton = None
    # Reset rate limiter to prevent cross-test pollution (matches app fixture teardown)
    from jellyswipe.rate_limiter import rate_limiter as _rl

    _rl.reset()


@pytest.fixture
def client_real_auth(app_real_auth):
    """TestClient backed by real require_auth — for auth integration tests only."""
    with TestClient(app_real_auth) as test_client:
        yield test_client
