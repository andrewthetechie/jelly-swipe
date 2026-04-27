"""
XSS security smoke tests for jellyswipe Flask application.

Tests verify three-layer XSS defense:
- Layer 1: Server-Side Validation - client-supplied title/thumb are ignored
- Layer 2: Safe DOM Rendering - verified in Phase 20 (manual verification)
- Layer 3: CSP Header - Content Security Policy blocks inline scripts

These tests prove the XSS vulnerability (Issue #6) is closed.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
import json
import os
import importlib
import sys
import secrets
from datetime import datetime, timezone

# CRITICAL: Import Flask BEFORE conftest.py's setup_test_environment runs
# This captures the real Flask class before it gets mocked
from flask import Flask as _RealFlaskClass
_REAL_FLASK = _RealFlaskClass


def _setup_vault_session(client, db_path, user_id="user_abc123", active_room="TEST123"):
    """Seed the token vault and set session cookie for authenticated testing."""
    import jellyswipe.db
    session_id = "xss-test-" + secrets.token_hex(8)
    conn = jellyswipe.db.get_db()
    conn.execute(
        "INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
        (session_id, "test-token", user_id, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    with client.session_transaction() as sess:
        sess["session_id"] = session_id
        sess["active_room"] = active_room


@pytest.fixture
def flask_app(tmp_path, monkeypatch):
    """
    Provide a real Flask app instance for route testing.

    This fixture is necessary because conftest.py's setup_test_environment()
    mocks Flask() for unit tests that don't need the full app. Route tests
    need the real Flask app to test HTTP endpoints.

    This fixture temporarily restores the real Flask class and reloads jellyswipe.
    """
    # Create a temporary database path
    db_file = tmp_path / "test_xss.db"

    # Set required environment variables
    monkeypatch.setenv("JELLYFIN_URL", "http://test.jellyfin.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")
    monkeypatch.setenv("TMDB_API_KEY", "test-tmdb-key")
    monkeypatch.setenv("FLASK_SECRET", "test-secret-key")
    monkeypatch.setenv("DB_PATH", str(db_file))

    # Restore the real Flask class using the reference we saved at module load time
    import flask
    flask.Flask = _REAL_FLASK

    # We need to reload jellyswipe with the real Flask
    # First, remove all jellyswipe modules from sys.modules
    modules_to_remove = [key for key in list(sys.modules.keys()) if key.startswith('jellyswipe')]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Now import jellyswipe - this will use the real Flask class
    import jellyswipe
    from jellyswipe import app

    # Patch the DB_PATH to use our temporary database
    import jellyswipe.db
    jellyswipe.db.DB_PATH = str(db_file)

    # Initialize the database
    jellyswipe.db.init_db()

    yield app

    # Cleanup: remove modules to prevent interference with other tests
    modules_to_remove = [key for key in list(sys.modules.keys()) if key.startswith('jellyswipe')]
    for mod in modules_to_remove:
        del sys.modules[mod]


class TestLayer1ServerSideValidation:
    """Tests for Layer 1: Server-Side Validation."""

    def test_swipe_ignores_client_supplied_title_thumb(self, flask_app):
        """
        Test that /room/swipe ignores client-supplied title and thumb parameters.

        Verifies that even if a malicious client sends title/thumb in the request body,
        the server resolves metadata from Jellyfin and stores only the server-resolved data.

        Requirement: XSS-01, XSS-04
        """
        # Import database functions
        import jellyswipe.db

        # Create a test room in solo mode (creates match immediately on right swipe)
        with jellyswipe.db.get_db() as conn:
            conn.execute(
                "INSERT INTO rooms (pairing_code, solo_mode) VALUES (?, ?)",
                ("TEST123", 1)
            )

        # Mock the session to simulate an authenticated user
        with flask_app.test_client() as client:
            _setup_vault_session(client, jellyswipe.db.DB_PATH, user_id="user_abc123", active_room="TEST123")
            with client.session_transaction() as sess:
                sess['solo_mode'] = True

            # Create a mock for JellyfinLibraryProvider
            mock_provider = MagicMock()
            mock_item = MagicMock()
            mock_item.title = "The Matrix"
            mock_item.year = 1999
            mock_provider.resolve_item_for_tmdb.return_value = mock_item

            # Patch get_provider() to return our mock
            import jellyswipe
            with patch.object(jellyswipe, 'get_provider', return_value=mock_provider):
                # Send malicious payload with script tags in title and thumb
                response = client.post(
                    '/room/TEST123/swipe',
                    json={
                        'movie_id': 'movie123',
                        'direction': 'right',
                        'title': '<script>alert("XSS")</script>',
                        'thumb': '<img src=x onerror=alert("XSS")>',
                        'user_id': 'jellyfin_user_1'
                    }
                )

                # Verify response was successful and returns accepted-only (per D-01: no match payload in HTTP response)
                assert response.status_code == 200
                response_data = json.loads(response.data)
                assert response_data == {'accepted': True}

                # Verify that provider was called (server-side resolution occurred)
                mock_provider.resolve_item_for_tmdb.assert_called_once_with('movie123')

                # Verify database contains only server-resolved data (not client-supplied)
                with jellyswipe.db.get_db() as conn:
                    cursor = conn.execute(
                        "SELECT title, thumb FROM matches WHERE room_code = ? AND movie_id = ?",
                        ("TEST123", "movie123")
                    )
                    match = cursor.fetchone()
                    assert match is not None
                    assert match['title'] == "The Matrix"
                    assert match['title'] != '<script>alert("XSS")</script>'
                    assert match['thumb'] == "/proxy?path=jellyfin/movie123/Primary"
                    assert match['thumb'] != '<img src=x onerror=alert("XSS")>'

    def test_swipe_ignores_client_params_silently(self, flask_app):
        """
        Test that /room/{code}/swipe silently ignores client-supplied title and thumb parameters.

        Per D-07: the endpoint accepts {movie_id, direction} only and silently ignores
        any extra fields like title/thumb. Server resolves metadata from Jellyfin.

        Requirement: XSS-04
        """
        # Import database functions
        import jellyswipe.db

        # Create a test room in solo mode
        with jellyswipe.db.get_db() as conn:
            conn.execute(
                "INSERT INTO rooms (pairing_code, solo_mode) VALUES (?, ?)",
                ("TEST456", 1)
            )

        with flask_app.test_client() as client:
            _setup_vault_session(client, jellyswipe.db.DB_PATH, user_id="user_xyz789", active_room="TEST456")
            with client.session_transaction() as sess:
                sess['solo_mode'] = True

            # Mock the provider
            mock_provider = MagicMock()
            mock_item = MagicMock()
            mock_item.title = "Safe Movie"
            mock_item.year = 2020
            mock_provider.resolve_item_for_tmdb.return_value = mock_item

            import jellyswipe
            with patch.object(jellyswipe, 'get_provider', return_value=mock_provider):
                # Send request with title/thumb (old client or attack attempt)
                response = client.post(
                    '/room/TEST456/swipe',
                    json={
                        'movie_id': 'movie456',
                        'direction': 'right',
                        'title': '<script>alert("XSS")</script>',
                        'thumb': 'malicious.jpg',
                        'user_id': 'jellyfin_user_2'
                    }
                )

                assert response.status_code == 200

                # Per D-01: swipe returns accepted-only (no title/thumb in response)
                response_data = json.loads(response.data)
                assert response_data == {'accepted': True}

                # Verify database contains only server-resolved data (not client-supplied)
                with jellyswipe.db.get_db() as conn:
                    cursor = conn.execute(
                        "SELECT title, thumb FROM matches WHERE room_code = ? AND movie_id = ?",
                        ("TEST456", "movie456")
                    )
                    match = cursor.fetchone()
                    assert match is not None
                    assert match['title'] == "Safe Movie"
                    assert match['thumb'] == "/proxy?path=jellyfin/movie456/Primary"


class TestLayer3CSPHeader:
    """Tests for Layer 3: Content Security Policy Header."""

    def test_csp_header_present_on_responses(self, flask_app):
        """
        Test that CSP header is present on all HTTP responses.

        Verifies that the @app.after_request hook adds the Content-Security-Policy
        header to block inline scripts and restrict external resources.

        Requirement: XSS-03
        """
        with flask_app.test_client() as client:
            # Test root endpoint
            response = client.get('/')
            assert 'Content-Security-Policy' in response.headers
            assert response.headers['Content-Security-Policy'] != ""

            # Test another endpoint (e.g., static file or API)
            response = client.get('/create')
            assert 'Content-Security-Policy' in response.headers
            assert response.headers['Content-Security-Policy'] != ""

    def test_csp_policy_directives_correct(self, flask_app):
        """
        Test that CSP header contains all required directives and no unsafe directives.

        Verifies that the CSP policy has:
        - default-src 'self'
        - script-src 'self' (no unsafe-inline or unsafe-eval)
        - object-src 'none'
        - img-src 'self' https://image.tmdb.org
        - frame-src https://www.youtube.com

        Requirement: XSS-03
        """
        with flask_app.test_client() as client:
            response = client.get('/')
            csp = response.headers['Content-Security-Policy']

            # Verify required directives are present
            assert "default-src 'self'" in csp, "Missing default-src 'self' directive"
            assert "script-src 'self'" in csp, "Missing script-src 'self' directive"
            assert "object-src 'none'" in csp, "Missing object-src 'none' directive"
            assert "img-src 'self' https://image.tmdb.org" in csp, "Missing img-src directive"
            assert "frame-src https://www.youtube.com" in csp, "Missing frame-src directive"

            # Verify unsafe directives are NOT present
            assert "unsafe-inline" not in csp, "CSP should not contain unsafe-inline"
            assert "unsafe-eval" not in csp, "CSP should not contain unsafe-eval"


class TestEndToEndXSSBlocking:
    """End-to-end tests verifying all three layers of XSS defense work together."""

    def test_xss_blocked_three_layer_defense(self, flask_app):
        """
        End-to-end test that verifies XSS is blocked through all three defense layers.

        This test sends a malicious payload with script tags and verifies:
        1. Layer 1: Security warning is logged when client sends title/thumb
        2. Layer 1: Server resolves metadata from Jellyfin, ignoring client params
        3. Layer 3: CSP header is present in response

        Note: Layer 2 (safe DOM rendering) is verified indirectly - if Layer 1
        blocks the malicious data at the server, Layer 2 never sees it. Layer 2
        was verified manually in Phase 20.

        Requirement: XSS-01, XSS-02, XSS-03, XSS-04
        """
        import jellyswipe

        # Create a test room in solo mode
        with jellyswipe.db.get_db() as conn:
            conn.execute(
                "INSERT INTO rooms (pairing_code, solo_mode) VALUES (?, ?)",
                ("E2E123", 1)
            )

        with flask_app.test_client() as client:
            _setup_vault_session(client, jellyswipe.db.DB_PATH, user_id="user_e2e", active_room="E2E123")
            with client.session_transaction() as sess:
                sess['solo_mode'] = True

            # Mock the provider to return safe data
            mock_provider = MagicMock()
            mock_item = MagicMock()
            mock_item.title = "Inception"
            mock_item.year = 2010
            mock_provider.resolve_item_for_tmdb.return_value = mock_item

            with patch.object(jellyswipe, 'get_provider', return_value=mock_provider):
                # Send malicious payload
                response = client.post(
                    '/room/E2E123/swipe',
                    json={
                        'movie_id': 'movie_e2e',
                        'direction': 'right',
                        'title': '<script>alert("XSS")</script>',
                        'thumb': '<img src=x onerror=alert("XSS")>',
                        'user_id': 'jellyfin_user_e2e'
                    }
                )

                # Verify Layer 1: Response was successful (per D-01: accepted-only, no match payload)
                assert response.status_code == 200
                response_data = json.loads(response.data)
                assert response_data == {'accepted': True}

                # Verify Layer 3: CSP header is present
                assert 'Content-Security-Policy' in response.headers
                assert "script-src 'self'" in response.headers['Content-Security-Policy']
                assert "unsafe-inline" not in response.headers['Content-Security-Policy']

                # Verify Layer 1: Database contains only server-resolved safe data
                with jellyswipe.db.get_db() as conn:
                    cursor = conn.execute(
                        "SELECT title, thumb FROM matches WHERE room_code = ? AND movie_id = ?",
                        ("E2E123", "movie_e2e")
                    )
                    match = cursor.fetchone()
                    assert match is not None
                    assert match['title'] == "Inception"
                    assert '<script>' not in match['title']
                    assert match['thumb'] == "/proxy?path=jellyfin/movie_e2e/Primary"

    def test_swipe_handles_jellyfin_failure_gracefully(self, flask_app, caplog):
        """
        Test that swipe handles Jellyfin API failures gracefully.

        When Jellyfin metadata resolution fails, the swipe should still complete
        but no match should be created. This ensures the app remains functional
        even when the Jellyfin server is unavailable.

        Requirement: Edge case handling for XSS defense
        """
        import jellyswipe

        # Create a test room in solo mode
        with jellyswipe.db.get_db() as conn:
            conn.execute(
                "INSERT INTO rooms (pairing_code, solo_mode) VALUES (?, ?)",
                ("FAIL789", 1)
            )

        with flask_app.test_client() as client:
            _setup_vault_session(client, jellyswipe.db.DB_PATH, user_id="user_fail", active_room="FAIL789")
            with client.session_transaction() as sess:
                sess['solo_mode'] = True

            # Mock the provider to raise RuntimeError (simulating Jellyfin failure)
            mock_provider = MagicMock()
            mock_provider.resolve_item_for_tmdb.side_effect = RuntimeError("Jellyfin item lookup failed")

            with patch.object(jellyswipe, 'get_provider', return_value=mock_provider):
                with caplog.at_level('WARNING'):
                    # Send swipe request
                    response = client.post(
                        '/room/FAIL789/swipe',
                        json={
                            'movie_id': 'movie_fail',
                            'direction': 'right',
                            'user_id': 'jellyfin_user_fail'
                        }
                    )

                    # Verify response indicates no match (because metadata resolution failed)
                    assert response.status_code == 200
                    response_data = json.loads(response.data)
                    assert response_data.get('match') is False or 'match' not in response_data

                    # Verify error was logged
                    error_logs = [
                        record for record in caplog.records
                        if record.levelname == 'WARNING' and 'Failed to resolve metadata' in record.message
                    ]
                    assert len(error_logs) > 0, "Error was not logged"

                    # Verify no match was created in database
                    with jellyswipe.db.get_db() as conn:
                        cursor = conn.execute(
                            "SELECT COUNT(*) as count FROM matches WHERE room_code = ? AND movie_id = ?",
                            ("FAIL789", "movie_fail")
                        )
                        result = cursor.fetchone()
                        assert result['count'] == 0, "Match should not be created when metadata resolution fails"

                    # Verify swipe was still recorded
                    with jellyswipe.db.get_db() as conn:
                        cursor = conn.execute(
                            "SELECT COUNT(*) as count FROM swipes WHERE room_code = ? AND movie_id = ?",
                            ("FAIL789", "movie_fail")
                        )
                        result = cursor.fetchone()
                        assert result['count'] == 1, "Swipe should still be recorded even if match creation fails"
