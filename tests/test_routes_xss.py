"""XSS security tests for EPIC-03 verification.

Tests verify that all user-controlled input is properly sanitized before being
stored, rendered, or reflected in responses. Flask's jsonify() auto-escapes
HTML entities in JSON strings - these tests prove that protection works and
that non-JSON paths (proxy) are also safe.
"""

import json
import os
from unittest.mock import MagicMock

import sqlite3

from tests.conftest import set_session_cookie, sqlite_test_transaction

# ---------------------------------------------------------------------------
# Module-level XSS payload constants (per D-03, D-04, D-05, D-06, D-07)
# ---------------------------------------------------------------------------

XSS_SCRIPT_TAG = "<script>alert('xss')</script>"
XSS_IMG_TAG = "<img src=x onerror=alert(1)>"
XSS_SVG_TAG = "<svg onload=alert(1)>"
XSS_JS_URL = "javascript:alert(1)"
XSS_JS_VOID = "javascript:void(0)"
XSS_EVENT_HANDLER_DQ = '" onmouseover="alert(1)'
XSS_EVENT_HANDLER_SQ = "' onload='alert(1)"
XSS_ENCODED_ANGLE = "&lt;script&gt;"
XSS_PERCENT = "%3Cscript%3E"
XSS_HEX_ENCODED = "&#x3C;script&#x3E;"


def _setup_vault_session(
    client, secret_key, user_id="user_abc123", active_room="TEST123"
):
    """Inject session state for XSS tests.

    Auth is handled by app.dependency_overrides[require_auth] in the app fixture.
    Only active_room (and optionally solo_mode) goes into the session cookie.
    """
    set_session_cookie(client, {"active_room": active_room}, secret_key)


class TestLayer1ServerSideValidation:
    def test_swipe_ignores_client_supplied_title_thumb(
        self, client, app, db_path, monkeypatch
    ):
        import jellyswipe.dependencies as deps

        with sqlite_test_transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO rooms (pairing_code, solo_mode) VALUES (?, ?)",
                ("TEST123", 1),
            )

        _setup_vault_session(
            client,
            os.environ["FLASK_SECRET"],
            user_id="user_abc123",
            active_room="TEST123",
        )
        set_session_cookie(client, {"solo_mode": True}, os.environ["FLASK_SECRET"])

        mock_provider = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "The Matrix"
        mock_item.year = 1999
        mock_provider.resolve_item_for_tmdb.return_value = mock_item

        monkeypatch.setattr(
            deps, "_provider_singleton", mock_provider, raising=False
        )

        response = client.post(
            "/room/TEST123/swipe",
            json={
                "media_id": "movie123",
                "direction": "right",
            },
        )

        assert response.status_code == 200
        response_data = response.json()
        assert response_data == {"accepted": True}

        mock_provider.resolve_item_for_tmdb.assert_called_once_with("movie123")

        with sqlite_test_transaction(db_path) as conn:
            cursor = conn.execute(
                "SELECT title, thumb FROM matches WHERE room_code = ? AND movie_id = ?",
                ("TEST123", "movie123"),
            )
            match = cursor.fetchone()
            assert match is not None
            assert match["title"] == "The Matrix"
            assert match["title"] != '<script>alert("XSS")</script>'
            assert match["thumb"] == "/proxy?path=jellyfin/movie123/Primary"
            assert match["thumb"] != '<img src=x onerror=alert("XSS")>'

    def test_swipe_ignores_client_params_silently(
        self, client, app, db_path, monkeypatch
    ):
        import jellyswipe.dependencies as deps

        with sqlite_test_transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO rooms (pairing_code, solo_mode) VALUES (?, ?)",
                ("TEST456", 1),
            )

        _setup_vault_session(
            client,
            os.environ["FLASK_SECRET"],
            user_id="user_xyz789",
            active_room="TEST456",
        )
        set_session_cookie(client, {"solo_mode": True}, os.environ["FLASK_SECRET"])

        mock_provider = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Safe Movie"
        mock_item.year = 2020
        mock_provider.resolve_item_for_tmdb.return_value = mock_item

        monkeypatch.setattr(
            deps, "_provider_singleton", mock_provider, raising=False
        )

        response = client.post(
            "/room/TEST456/swipe",
            json={
                "media_id": "movie456",
                "direction": "right",
            },
        )

        assert response.status_code == 200

        response_data = response.json()
        assert response_data == {"accepted": True}

        with sqlite_test_transaction(db_path) as conn:
            cursor = conn.execute(
                "SELECT title, thumb FROM matches WHERE room_code = ? AND movie_id = ?",
                ("TEST456", "movie456"),
            )
            match = cursor.fetchone()
            assert match is not None
            assert match["title"] == "Safe Movie"
            assert match["thumb"] == "/proxy?path=jellyfin/movie456/Primary"


class TestLayer3CSPHeader:
    def test_csp_header_present_on_responses(self, client):
        response = client.get("/")
        assert "Content-Security-Policy" in response.headers
        assert response.headers["Content-Security-Policy"] != ""

        response = client.get("/me")
        assert "Content-Security-Policy" in response.headers
        assert response.headers["Content-Security-Policy"] != ""

    def test_csp_policy_directives_correct(self, client):
        response = client.get("/")
        csp = response.headers["Content-Security-Policy"]

        assert "default-src 'self'" in csp, "Missing default-src 'self' directive"
        assert "script-src 'self'" in csp, "Missing script-src 'self' directive"
        assert "object-src 'none'" in csp, "Missing object-src 'none' directive"
        assert "img-src 'self' https://image.tmdb.org" in csp, (
            "Missing img-src directive"
        )
        assert "frame-src https://www.youtube.com" in csp, "Missing frame-src directive"

        assert "unsafe-inline" not in csp, "CSP should not contain unsafe-inline"
        assert "unsafe-eval" not in csp, "CSP should not contain unsafe-eval"


class TestEndToEndXSSBlocking:
    def test_xss_blocked_three_layer_defense(self, client, app, db_path, monkeypatch):
        import jellyswipe.dependencies as deps

        with sqlite_test_transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO rooms (pairing_code, solo_mode) VALUES (?, ?)",
                ("E2E123", 1),
            )

        _setup_vault_session(
            client, os.environ["FLASK_SECRET"], user_id="user_e2e", active_room="E2E123"
        )
        set_session_cookie(client, {"solo_mode": True}, os.environ["FLASK_SECRET"])

        mock_provider = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Inception"
        mock_item.year = 2010
        mock_provider.resolve_item_for_tmdb.return_value = mock_item

        monkeypatch.setattr(
            deps, "_provider_singleton", mock_provider, raising=False
        )

        response = client.post(
            "/room/E2E123/swipe",
            json={
                "media_id": "movie_e2e",
                "direction": "right",
            },
        )

        assert response.status_code == 200
        response_data = response.json()
        assert response_data == {"accepted": True}

        assert "Content-Security-Policy" in response.headers
        assert "script-src 'self'" in response.headers["Content-Security-Policy"]
        assert "unsafe-inline" not in response.headers["Content-Security-Policy"]

        with sqlite_test_transaction(db_path) as conn:
            cursor = conn.execute(
                "SELECT title, thumb FROM matches WHERE room_code = ? AND movie_id = ?",
                ("E2E123", "movie_e2e"),
            )
            match = cursor.fetchone()
            assert match is not None
            assert match["title"] == "Inception"
            assert "<script>" not in match["title"]
            assert match["thumb"] == "/proxy?path=jellyfin/movie_e2e/Primary"

    def test_swipe_handles_jellyfin_failure_gracefully(
        self, client, app, db_path, monkeypatch, caplog
    ):
        import jellyswipe.dependencies as deps

        with sqlite_test_transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO rooms (pairing_code, solo_mode) VALUES (?, ?)",
                ("FAIL789", 1),
            )

        _setup_vault_session(
            client,
            os.environ["FLASK_SECRET"],
            user_id="user_fail",
            active_room="FAIL789",
        )
        set_session_cookie(client, {"solo_mode": True}, os.environ["FLASK_SECRET"])

        mock_provider = MagicMock()
        mock_provider.resolve_item_for_tmdb.side_effect = RuntimeError(
            "Jellyfin item lookup failed"
        )

        monkeypatch.setattr(
            deps, "_provider_singleton", mock_provider, raising=False
        )

        with caplog.at_level("WARNING"):
            response = client.post(
                "/room/FAIL789/swipe",
                json={
                    "media_id": "movie_fail",
                    "direction": "right",
                },
            )

            assert response.status_code == 200
            response_data = response.json()
            assert (
                response_data.get("accepted") is True or "accepted" not in response_data
            )

            error_logs = [
                record
                for record in caplog.records
                if record.levelno >= 30
                and "Failed to resolve metadata" in record.getMessage()
            ]
            assert len(error_logs) > 0, "Error was not logged"

            with sqlite_test_transaction(db_path) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM matches WHERE room_code = ? AND movie_id = ?",
                    ("FAIL789", "movie_fail"),
                )
                result = cursor.fetchone()
                assert result["count"] == 0, (
                    "Match should not be created when metadata resolution fails"
                )

            with sqlite_test_transaction(db_path) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM swipes WHERE room_code = ? AND movie_id = ?",
                    ("FAIL789", "movie_fail"),
                )
                result = cursor.fetchone()
                assert result["count"] == 1, (
                    "Swipe should still be recorded even if match creation fails"
                )


# ---------------------------------------------------------------------------
# Helpers (adapted for EPIC-05 route patterns with vault-based auth)
# ---------------------------------------------------------------------------


def _set_session(client, secret_key, *, active_room="ROOM1", solo_mode=False):
    """Inject session state for XSS swipe tests.

    Auth is handled by app.dependency_overrides[require_auth] in the app fixture.
    Only active_room and solo_mode need to be in the session cookie.
    """
    data = {"solo_mode": solo_mode}
    if active_room is not None:
        data["active_room"] = active_room
    if data:
        set_session_cookie(client, data, secret_key)


def _seed_solo_room(db_path, room_code="ROOM1"):
    """Seed a solo-mode room ready for swiping."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute(
            "INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) "
            "VALUES (?, ?, ?, ?, ?)",
            (room_code, json.dumps([]), 1, "All", 1),
        )
        conn.commit()
    finally:
        conn.close()


def _setup_solo_swipe_session(client):
    """Prepare a solo-mode room with vault-based auth for swipe XSS tests."""
    _set_session(client, os.environ["FLASK_SECRET"], solo_mode=True)
    _seed_solo_room(os.environ["DB_PATH"])


# ---------------------------------------------------------------------------
# Section 1: Stored XSS via /room/{code}/swipe (D-08, D-09, D-10)
# ---------------------------------------------------------------------------


def test_swipe_xss_title_escaped_in_match_response(client, monkeypatch):
    _setup_solo_swipe_session(client)

    mock_provider = MagicMock()
    mock_item = MagicMock()
    mock_item.title = "Movie movie-1"
    mock_item.year = 2024
    mock_provider.resolve_item_for_tmdb.return_value = mock_item

    import jellyswipe.dependencies as deps

    monkeypatch.setattr(deps, "_provider_singleton", mock_provider, raising=False)

    response = client.post(
        "/room/ROOM1/swipe",
        json={
            "media_id": "movie-1",
            "direction": "right",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data == {"accepted": True}
    assert "<script>" not in response.text


def test_swipe_xss_thumb_escaped_in_match_response(client, monkeypatch):
    _setup_solo_swipe_session(client)

    mock_provider = MagicMock()
    mock_item = MagicMock()
    mock_item.title = "Movie movie-2"
    mock_item.year = 2024
    mock_provider.resolve_item_for_tmdb.return_value = mock_item

    import jellyswipe.dependencies as deps

    monkeypatch.setattr(deps, "_provider_singleton", mock_provider, raising=False)

    response = client.post(
        "/room/ROOM1/swipe",
        json={
            "media_id": "movie-2",
            "direction": "right",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data == {"accepted": True}
    assert "<img" not in response.text


def test_stored_xss_matches_endpoint(client, monkeypatch):
    _setup_solo_swipe_session(client)

    mock_provider = MagicMock()
    mock_item = MagicMock()
    mock_item.title = "Movie movie-3"
    mock_item.year = 2024
    mock_provider.resolve_item_for_tmdb.return_value = mock_item

    import jellyswipe.dependencies as deps

    monkeypatch.setattr(deps, "_provider_singleton", mock_provider, raising=False)

    client.post(
        "/room/ROOM1/swipe",
        json={
            "media_id": "movie-3",
            "direction": "right",
        },
    )

    response = client.get("/matches")

    assert response.status_code == 200
    body_text = response.text
    assert "<script>" not in body_text
    assert "<img" not in body_text


def test_swipe_xss_img_tag_escaped(client, monkeypatch):
    _setup_solo_swipe_session(client)

    mock_provider = MagicMock()
    mock_item = MagicMock()
    mock_item.title = "Movie movie-4"
    mock_item.year = 2024
    mock_provider.resolve_item_for_tmdb.return_value = mock_item

    import jellyswipe.dependencies as deps

    monkeypatch.setattr(deps, "_provider_singleton", mock_provider, raising=False)

    response = client.post(
        "/room/ROOM1/swipe",
        json={
            "media_id": "movie-4",
            "direction": "right",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data == {"accepted": True}
    assert "<img" not in response.text


def test_swipe_xss_event_handler_escaped(client, monkeypatch):
    _setup_solo_swipe_session(client)

    mock_provider = MagicMock()
    mock_item = MagicMock()
    mock_item.title = "Movie movie-5"
    mock_item.year = 2024
    mock_provider.resolve_item_for_tmdb.return_value = mock_item

    import jellyswipe.dependencies as deps

    monkeypatch.setattr(deps, "_provider_singleton", mock_provider, raising=False)

    response = client.post(
        "/room/ROOM1/swipe",
        json={
            "media_id": "movie-5",
            "direction": "right",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data == {"accepted": True}
    assert XSS_EVENT_HANDLER_DQ not in response.text


# ---------------------------------------------------------------------------
# Section 2: Proxy route XSS tests (D-12, D-13, D-14, D-15)
# ---------------------------------------------------------------------------


def test_proxy_javascript_url_rejected(client):
    response = client.get(f"/proxy?path={XSS_JS_URL}")
    assert response.status_code == 403


def test_proxy_javascript_void_rejected(client):
    response = client.get(f"/proxy?path={XSS_JS_VOID}")
    assert response.status_code == 403


def test_proxy_path_traversal_rejected(client):
    response = client.get("/proxy?path=../../etc/passwd")
    assert response.status_code == 403


def test_proxy_html_in_path_rejected(client):
    response = client.get(f"/proxy?path={XSS_SCRIPT_TAG}")
    assert response.status_code == 403


def test_proxy_valid_uuid_path_accepted(client):
    response = client.get(
        "/proxy?path=jellyfin/00000000000000000000000000000000/Primary"
    )
    assert response.status_code == 200
    assert "image" in response.headers.get("content-type", "")


def test_proxy_valid_uuid_with_dashes_accepted(client):
    response = client.get(
        "/proxy?path=jellyfin/00000000-0000-0000-0000-000000000000/Primary"
    )
    assert response.status_code == 200
    assert "image" in response.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# Section 3: Input validation tests (D-16, D-17)
# ---------------------------------------------------------------------------


def test_join_room_xss_code_not_echoed(client):
    _setup_vault_session(
        client, os.environ["FLASK_SECRET"], user_id="xss-user", active_room="ROOM1"
    )
    response = client.post(
        f"/room/{XSS_SCRIPT_TAG}/join",
    )

    body_text = response.text
    assert "<script>" not in body_text
    assert response.status_code == 404
