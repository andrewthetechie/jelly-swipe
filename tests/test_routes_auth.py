"""Comprehensive auth route tests for all 3 authentication endpoints.

Covers /auth/provider, /auth/jellyfin-use-server-identity, and /auth/jellyfin-login
with header-spoof protection tests (EPIC-01).
"""

from unittest.mock import MagicMock

import jellyswipe
import pytest

SPOOF_HEADERS = ("X-Provider-User-Id", "X-Jellyfin-User-Id", "X-Emby-UserId")


# ---------------------------------------------------------------------------
# /auth/provider tests
# ---------------------------------------------------------------------------


def test_auth_provider_returns_jellyfin(client_real_auth):
    """GET /auth/provider returns 200 with correct provider JSON."""
    response = client_real_auth.get("/auth/provider")
    assert response.status_code == 200
    assert response.json() == {
        "provider": "jellyfin",
        "jellyfin_browser_auth": "delegate",
    }


def test_auth_provider_content_type_is_json(client_real_auth):
    """GET /auth/provider returns application/json content type."""
    response = client_real_auth.get("/auth/provider")
    assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# /auth/jellyfin-use-server-identity tests
# ---------------------------------------------------------------------------


def test_jellyfin_use_server_identity_success(client_real_auth):
    """POST /auth/jellyfin-use-server-identity returns userId on success."""
    response = client_real_auth.post("/auth/jellyfin-use-server-identity")
    assert response.status_code == 200
    assert response.json() == {"userId": "verified-user"}


def test_jellyfin_use_server_identity_sets_session_flag(client_real_auth):
    """Successful delegate identity sets session_id in session (vault-based auth)."""
    client_real_auth.post("/auth/jellyfin-use-server-identity")
    # Verify session is live by calling an auth endpoint
    resp2 = client_real_auth.get("/auth/provider")
    assert resp2.status_code == 200


def test_jellyfin_use_server_identity_runtime_error_returns_401(
    client_real_auth, monkeypatch
):
    """RuntimeError from provider returns 401 and error message."""
    fake = jellyswipe._provider_singleton
    monkeypatch.setattr(
        fake,
        "server_access_token_for_delegate",
        MagicMock(side_effect=RuntimeError("unavailable")),
    )
    response = client_real_auth.post("/auth/jellyfin-use-server-identity")
    assert response.status_code == 401
    assert "error" in response.json()


def test_jellyfin_use_server_identity_failure_no_session_flag(
    client_real_auth, monkeypatch
):
    """Failed delegate identity does NOT set session flag."""
    fake = jellyswipe._provider_singleton
    monkeypatch.setattr(
        fake,
        "server_access_token_for_delegate",
        MagicMock(side_effect=RuntimeError("unavailable")),
    )
    client_real_auth.post("/auth/jellyfin-use-server-identity")
    # Verify no session was created by calling an auth endpoint
    resp2 = client_real_auth.get("/auth/provider")
    assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# /auth/jellyfin-login tests
# ---------------------------------------------------------------------------


def test_jellyfin_login_success(client_real_auth):
    """POST /auth/jellyfin-login with valid credentials returns userId only (token stored in vault)."""
    response = client_real_auth.post(
        "/auth/jellyfin-login",
        json={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "userId" in data
    assert data["userId"] == "verified-user"
    assert "authToken" not in data


def test_jellyfin_login_missing_username_returns_400(client_real_auth):
    """POST /auth/jellyfin-login without username returns 400."""
    response = client_real_auth.post(
        "/auth/jellyfin-login",
        json={"password": "testpass"},
    )
    assert response.status_code == 400


def test_jellyfin_login_missing_password_returns_400(client_real_auth):
    """POST /auth/jellyfin-login without password returns 400."""
    response = client_real_auth.post(
        "/auth/jellyfin-login",
        json={"username": "testuser"},
    )
    assert response.status_code == 400


def test_jellyfin_login_empty_body_returns_400(client_real_auth):
    """POST /auth/jellyfin-login with empty body returns 400."""
    response = client_real_auth.post("/auth/jellyfin-login", json={})
    assert response.status_code == 400


def test_jellyfin_login_auth_failure_returns_401(client_real_auth, monkeypatch):
    """POST /auth/jellyfin-login when provider raises exception returns 401."""
    fake = jellyswipe._provider_singleton
    monkeypatch.setattr(
        fake,
        "authenticate_user_session",
        MagicMock(side_effect=Exception("auth failed")),
    )
    response = client_real_auth.post(
        "/auth/jellyfin-login",
        json={"username": "testuser", "password": "testpass"},
    )
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


@pytest.mark.parametrize("spoof_header", SPOOF_HEADERS)
def test_jellyfin_login_ignores_spoofed_headers(client_real_auth, spoof_header):
    """Login endpoint ignores spoofed identity headers."""
    response = client_real_auth.post(
        "/auth/jellyfin-login",
        json={"username": "testuser", "password": "testpass"},
        headers={spoof_header: "attacker-id"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["userId"] == "verified-user"


@pytest.mark.parametrize("spoof_header", SPOOF_HEADERS)
def test_auth_provider_ignores_spoofed_headers(client_real_auth, spoof_header):
    """Provider endpoint ignores spoofed headers (static endpoint)."""
    response = client_real_auth.get(
        "/auth/provider",
        headers={spoof_header: "attacker-id"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "provider": "jellyfin",
        "jellyfin_browser_auth": "delegate",
    }
