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

# CRITICAL: Import Flask BEFORE conftest.py's setup_test_environment runs
# This captures the real Flask class before it gets mocked
from flask import Flask as _RealFlaskClass
_REAL_FLASK = _RealFlaskClass


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
            with client.session_transaction() as sess:
                sess['active_room'] = 'TEST123'
                sess['my_user_id'] = 'user_abc123'
                sess['solo_mode'] = True

            # Create a mock for JellyfinLibraryProvider
            mock_provider = MagicMock()
            mock_item = MagicMock()
            mock_item.title = "The Matrix"
            mock_item.year = 1999
            mock_provider.resolve_item_for_tmdb.return_value = mock_item

            # Patch get_provider() to return our mock
            # Need to patch in the module where it's imported
            import jellyswipe
            with patch.object(jellyswipe, 'get_provider', return_value=mock_provider):
                # Send malicious payload with script tags in title and thumb
                response = client.post(
                    '/room/swipe',
                    json={
                        'movie_id': 'movie123',
                        'direction': 'right',
                        'title': '<script>alert("XSS")</script>',
                        'thumb': '<img src=x onerror=alert("XSS")>',
                        'user_id': 'jellyfin_user_1'
                    }
                )

                # Verify response was successful
                assert response.status_code == 200

                # Verify that the response contains server-resolved title, not client-supplied
                response_data = json.loads(response.data)
                assert response_data['title'] == "The Matrix"
                assert response_data['title'] != '<script>alert("XSS")</script>'

                # Verify that provider was called (server-side resolution occurred)
                mock_provider.resolve_item_for_tmdb.assert_called_once_with('movie123')

                # Verify database contains only server-resolved data
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

    def test_swipe_logs_security_warning_for_client_params(self, flask_app, caplog):
        """
        Test that /room/swipe logs a security warning when client sends title/thumb parameters.

        Verifies that the server detects and logs potential XSS attempts when a client
        sends title/thumb parameters (which should not be sent).

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
            with client.session_transaction() as sess:
                sess['active_room'] = 'TEST456'
                sess['my_user_id'] = 'user_xyz789'
                sess['solo_mode'] = True

            # Mock the provider
            mock_provider = MagicMock()
            mock_item = MagicMock()
            mock_item.title = "Safe Movie"
            mock_item.year = 2020
            mock_provider.resolve_item_for_tmdb.return_value = mock_item

            # Patch get_provider() and capture logs
            import jellyswipe
            with patch.object(jellyswipe, 'get_provider', return_value=mock_provider):
                with caplog.at_level('WARNING'):
                    # Send request with title/thumb (old client or attack attempt)
                    response = client.post(
                        '/room/swipe',
                        json={
                            'movie_id': 'movie456',
                            'direction': 'right',
                            'title': '<script>alert("XSS")</script>',
                            'thumb': 'malicious.jpg',
                            'user_id': 'jellyfin_user_2'
                        }
                    )

                    assert response.status_code == 200

                    # Verify that a security warning was logged
                    warning_logs = [
                        record for record in caplog.records
                        if record.levelname == 'WARNING' and 'Security warning' in record.message
                    ]
                    assert len(warning_logs) > 0, "Security warning was not logged"

                    # Verify the log message contains expected details
                    warning_message = warning_logs[0].message
                    assert 'Client sent title/thumb parameters' in warning_message
                    assert 'movie_id=movie456' in warning_message
                    assert '<script>alert("XSS")</script>' in warning_message


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
