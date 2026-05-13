"""Comprehensive auth route tests for delegate identity and 404 regression guards.

Covers /auth/jellyfin-use-server-identity with header-spoof protection tests (EPIC-01),
404 regression tests for removed routes, and E2E delegate login/logout flow.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jellyswipe.dependencies as deps
import pytest

SPOOF_HEADERS = ("X-Provider-User-Id", "X-Jellyfin-User-Id", "X-Emby-UserId")


# ---------------------------------------------------------------------------
# /auth/jellyfin-use-server-identity tests
# ---------------------------------------------------------------------------


def test_jellyfin_use_server_identity_success(client_real_auth):
    """POST /auth/jellyfin-use-server-identity returns userId on success."""
    response = client_real_auth.post("/auth/jellyfin-use-server-identity")
    assert response.status_code == 200
    assert response.json() == {"userId": "verified-user"}


def test_jellyfin_use_server_identity_runtime_error_returns_401(
    client_real_auth, monkeypatch
):
    """RuntimeError from provider returns 401 and error message."""
    fake = deps._provider_singleton
    monkeypatch.setattr(
        fake,
        "server_access_token_for_delegate",
        MagicMock(side_effect=RuntimeError("unavailable")),
    )
    response = client_real_auth.post("/auth/jellyfin-use-server-identity")
    assert response.status_code == 401
    assert "error" in response.json()


# ---------------------------------------------------------------------------
# EPIC-01 Header-Spoof tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spoof_header", SPOOF_HEADERS)
def test_jellyfin_use_server_identity_ignores_spoofed_headers(
    client_real_auth, spoof_header
):
    """Delegate identity endpoint ignores spoofed identity headers."""
    response = client_real_auth.post(
        "/auth/jellyfin-use-server-identity",
        headers={spoof_header: "attacker-id"},
    )
    assert response.status_code == 200
    assert response.json()["userId"] == "verified-user"


# ---------------------------------------------------------------------------
# 404 Regression tests for removed routes
# ---------------------------------------------------------------------------


def test_jellyfin_login_returns_404(client_real_auth):
    """POST /auth/jellyfin-login returns 404 (route removed)."""
    response = client_real_auth.post(
        "/auth/jellyfin-login",
        json={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 404


def test_auth_provider_returns_404(client_real_auth):
    """GET /auth/provider returns 404 (route removed)."""
    response = client_real_auth.get("/auth/provider")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# E2E delegate login/logout flow
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_delegate_login_me_logout_flow(client_real_auth):
    """Full E2E: delegate login -> GET /me -> logout -> GET /me returns 401."""
    # Step 1: Delegate login
    resp = client_real_auth.post("/auth/jellyfin-use-server-identity")
    assert resp.status_code == 200
    body = resp.json()
    assert "userId" in body
    # Step 2: Authenticated request
    me = client_real_auth.get("/me")
    assert me.status_code == 200
    assert "userId" in me.json()
    # Step 3: Logout
    logout = client_real_auth.post("/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["status"] == "logged_out"
    # Step 4: Unauthenticated
    me2 = client_real_auth.get("/me")
    assert me2.status_code == 401


# ---------------------------------------------------------------------------
# Expired session cleanup tests
# ---------------------------------------------------------------------------


def test_expired_sessions_cleaned_up_on_delegate_login(client_real_auth, db_connection):
    """Expired auth sessions are deleted when a new session is created."""
    # Seed an expired session (created 15 days ago)
    expired_sid = "expired-session-id"
    cutoff = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    db_connection.execute(
        "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
        (expired_sid, "old-token", "old-user", cutoff),
    )
    db_connection.commit()

    # Login creates a new session
    response = client_real_auth.post("/auth/jellyfin-use-server-identity")
    assert response.status_code == 200

    # Expired session should be gone
    row = db_connection.execute(
        "SELECT session_id FROM auth_sessions WHERE session_id = ?", (expired_sid,)
    ).fetchone()
    assert row is None

    # New session should exist
    new_user_id = response.json()["userId"]
    new_row = db_connection.execute(
        "SELECT session_id FROM auth_sessions WHERE jellyfin_user_id = ?",
        (new_user_id,),
    ).fetchone()
    assert new_row is not None
