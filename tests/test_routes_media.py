"""Tests for media route handlers with TMDB caching.

Tests cover cache hit/miss behavior for trailer and cast routes,
verifying that TMDB lookups are skipped on cache hits and that
cache misses are properly stored.
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import patch


from tests.conftest import set_session_cookie


def _sqlite_conn():
    path = os.environ["DB_PATH"]
    import sqlite3

    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _seed_cache(media_id, lookup_type, result_json):
    """Insert a cache row directly into the database with timezone-aware timestamp."""
    conn = _sqlite_conn()
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            "INSERT INTO tmdb_cache (media_id, lookup_type, result_json, fetched_at) "
            "VALUES (:media_id, :lookup_type, :result_json, :fetched_at)",
            {
                "media_id": media_id,
                "lookup_type": lookup_type,
                "result_json": result_json,
                "fetched_at": now,
            },
        )
        conn.commit()
    finally:
        conn.close()


def _set_session(client):
    """Inject session state for media route tests."""
    set_session_cookie(client, {"user_id": "verified-user"}, os.environ["FLASK_SECRET"])


# ---------------------------------------------------------------------------
# Trailer route tests
# ---------------------------------------------------------------------------


class TestTrailerRoute:
    """Tests for GET /get-trailer/{movie_id}."""

    def test_trailer_cache_hit_returns_cached_data(self, client, app):
        """Pre-populated cache returns cached youtube_key without TMDB calls."""
        _seed_cache("movie-1", "trailer", json.dumps({"youtube_key": "abc123"}))
        _set_session(client)

        with patch("jellyswipe.routers.media.lookup_trailer") as mock_lookup:
            resp = client.get("/get-trailer/movie-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["youtube_key"] == "abc123"
        mock_lookup.assert_not_called()

    def test_trailer_cache_hit_empty_result_returns_404(self, client, app):
        """Cached miss ({}) returns 404 without TMDB calls."""
        _seed_cache("movie-2", "trailer", json.dumps({}))
        _set_session(client)

        with patch("jellyswipe.routers.media.lookup_trailer") as mock_lookup:
            resp = client.get("/get-trailer/movie-2")

        assert resp.status_code == 404
        mock_lookup.assert_not_called()

    def test_trailer_cache_miss_stores_and_returns(self, client, app):
        """Cache miss resolves item, calls lookup_trailer, stores result, returns."""
        _set_session(client)

        with patch("jellyswipe.routers.media.lookup_trailer") as mock_lookup:
            mock_lookup.return_value = "xyz789"
            resp = client.get("/get-trailer/movie-3")

        assert resp.status_code == 200
        data = resp.json()
        assert data["youtube_key"] == "xyz789"
        mock_lookup.assert_called_once()

        # Verify it was stored in cache
        conn = _sqlite_conn()
        try:
            row = conn.execute(
                "SELECT result_json FROM tmdb_cache WHERE media_id = 'movie-3' AND lookup_type = 'trailer'"
            ).fetchone()
            assert row is not None
            assert json.loads(row["result_json"]) == {"youtube_key": "xyz789"}
        finally:
            conn.close()

    def test_trailer_cache_miss_no_trailer_stores_empty(self, client, app):
        """lookup_trailer returns None → route stores {}, returns 404."""
        _set_session(client)

        with patch("jellyswipe.routers.media.lookup_trailer") as mock_lookup:
            mock_lookup.return_value = None
            resp = client.get("/get-trailer/movie-4")

        assert resp.status_code == 404
        mock_lookup.assert_called_once()

        # Verify miss was cached
        conn = _sqlite_conn()
        try:
            row = conn.execute(
                "SELECT result_json FROM tmdb_cache WHERE media_id = 'movie-4' AND lookup_type = 'trailer'"
            ).fetchone()
            assert row is not None
            assert json.loads(row["result_json"]) == {}
        finally:
            conn.close()

    def test_trailer_second_call_hits_cache(self, client, app):
        """First call misses and stores; second call hits cache."""
        _set_session(client)

        with patch("jellyswipe.routers.media.lookup_trailer") as mock_lookup:
            mock_lookup.return_value = "first-call-key"
            resp1 = client.get("/get-trailer/movie-5")

        assert resp1.status_code == 200
        assert resp1.json()["youtube_key"] == "first-call-key"
        assert mock_lookup.call_count == 1

        # Second call — should hit cache
        with patch("jellyswipe.routers.media.lookup_trailer") as mock_lookup2:
            resp2 = client.get("/get-trailer/movie-5")

        assert resp2.status_code == 200
        assert resp2.json()["youtube_key"] == "first-call-key"
        mock_lookup2.assert_not_called()

    def test_trailer_item_lookup_failure_returns_404(self, client, app):
        """Jellyfin item resolution failure returns 404."""
        _set_session(client)

        from tests.conftest import FakeProvider
        import jellyswipe.config as app_config
        import jellyswipe as app_module
        from jellyswipe.dependencies import get_provider

        original = app_config._provider_singleton

        class FailingProvider(FakeProvider):
            def resolve_item_for_tmdb(self, movie_id):
                raise RuntimeError("item lookup failed")

        failing = FailingProvider()
        app_config._provider_singleton = failing
        app_module._provider_singleton = failing
        app.dependency_overrides[get_provider] = lambda: failing

        try:
            resp = client.get("/get-trailer/nonexistent")
            assert resp.status_code == 404
            assert "Movie metadata not found" in resp.json()["error"]
        finally:
            app_config._provider_singleton = original
            app_module._provider_singleton = original


# ---------------------------------------------------------------------------
# Cast route tests
# ---------------------------------------------------------------------------


class TestCastRoute:
    """Tests for GET /cast/{movie_id}."""

    def test_cast_cache_hit_returns_cached_data(self, client, app):
        """Pre-populated cache returns cached cast without TMDB calls."""
        cast_data = [
            {
                "name": "Actor 1",
                "character": "Role 1",
                "profile_path": "http://img/1.jpg",
            },
            {"name": "Actor 2", "character": "Role 2", "profile_path": None},
        ]
        _seed_cache("movie-10", "cast", json.dumps(cast_data))
        _set_session(client)

        with patch("jellyswipe.routers.media.lookup_cast") as mock_lookup:
            resp = client.get("/cast/movie-10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["cast"] == cast_data
        mock_lookup.assert_not_called()

    def test_cast_cache_miss_stores_and_returns(self, client, app):
        """Cache miss resolves item, calls lookup_cast, stores result, returns."""
        _set_session(client)
        expected_cast = [
            {"name": "Test Actor", "character": "Test Role", "profile_path": None}
        ]

        with patch("jellyswipe.routers.media.lookup_cast") as mock_lookup:
            mock_lookup.return_value = expected_cast
            resp = client.get("/cast/movie-11")

        assert resp.status_code == 200
        data = resp.json()
        assert data["cast"] == expected_cast
        mock_lookup.assert_called_once()

        # Verify it was stored in cache
        conn = _sqlite_conn()
        try:
            row = conn.execute(
                "SELECT result_json FROM tmdb_cache WHERE media_id = 'movie-11' AND lookup_type = 'cast'"
            ).fetchone()
            assert row is not None
            assert json.loads(row["result_json"]) == expected_cast
        finally:
            conn.close()

    def test_cast_route_empty_cast_stores_and_returns(self, client, app):
        """lookup_cast returns [] → route stores [], returns {"cast": []}."""
        _set_session(client)

        with patch("jellyswipe.routers.media.lookup_cast") as mock_lookup:
            mock_lookup.return_value = []
            resp = client.get("/cast/movie-12")

        assert resp.status_code == 200
        data = resp.json()
        assert data["cast"] == []
        mock_lookup.assert_called_once()

        # Verify empty cast was cached
        conn = _sqlite_conn()
        try:
            row = conn.execute(
                "SELECT result_json FROM tmdb_cache WHERE media_id = 'movie-12' AND lookup_type = 'cast'"
            ).fetchone()
            assert row is not None
            assert json.loads(row["result_json"]) == []
        finally:
            conn.close()

    def test_cast_item_lookup_failure_returns_404_with_empty_cast(self, client, app):
        """Jellyfin item resolution failure returns 404 with empty cast."""
        _set_session(client)

        from tests.conftest import FakeProvider
        import jellyswipe.config as app_config
        import jellyswipe as app_module
        from jellyswipe.dependencies import get_provider

        original = app_config._provider_singleton

        class FailingProvider(FakeProvider):
            def resolve_item_for_tmdb(self, movie_id):
                raise RuntimeError("item lookup failed")

        failing = FailingProvider()
        app_config._provider_singleton = failing
        app_module._provider_singleton = failing
        app.dependency_overrides[get_provider] = lambda: failing

        try:
            resp = client.get("/cast/nonexistent")
            assert resp.status_code == 404
            data = resp.json()
            assert "Movie metadata not found" in data["error"]
            assert data["cast"] == []
        finally:
            app_config._provider_singleton = original
            app_module._provider_singleton = original
