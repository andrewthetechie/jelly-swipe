"""Comprehensive proxy route tests for SSRF prevention via allowlist regex.

Covers /proxy endpoint: valid image paths, missing params, SSRF attack vectors,
server configuration, and provider error handling (EPIC-04).
"""

from unittest.mock import MagicMock

import jellyswipe
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_HEX32 = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
VALID_UUID36 = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


# ---------------------------------------------------------------------------
# Group 1: Valid path tests
# ---------------------------------------------------------------------------


def test_proxy_valid_hex32_path_returns_200(client):
    """Valid 32-char hex ID path returns 200."""
    response = client.get(f"/proxy?path=jellyfin/{VALID_HEX32}/Primary")
    assert response.status_code == 200


def test_proxy_valid_uuid36_path_returns_200(client):
    """Valid 36-char UUID path returns 200."""
    response = client.get(f"/proxy?path=jellyfin/{VALID_UUID36}/Primary")
    assert response.status_code == 200


def test_proxy_returns_image_data_from_provider(client, monkeypatch):
    """Image data from provider is returned in the response body."""
    fake = jellyswipe._provider_singleton
    monkeypatch.setattr(
        fake,
        "fetch_library_image",
        MagicMock(return_value=(b"\x89PNG\r\n", "image/png")),
    )
    response = client.get(f"/proxy?path=jellyfin/{VALID_HEX32}/Primary")
    assert response.status_code == 200
    assert response.content == b"\x89PNG\r\n"


def test_proxy_content_type_matches_provider(client, monkeypatch):
    """Content-type from provider is passed through to the HTTP response."""
    fake = jellyswipe._provider_singleton
    monkeypatch.setattr(
        fake,
        "fetch_library_image",
        MagicMock(return_value=(b"img", "image/webp")),
    )
    response = client.get(f"/proxy?path=jellyfin/{VALID_HEX32}/Primary")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"


# ---------------------------------------------------------------------------
# Group 2: Missing/empty path tests
# ---------------------------------------------------------------------------


def test_proxy_missing_path_returns_403(client):
    """Missing path parameter returns 403."""
    response = client.get("/proxy")
    assert response.status_code == 403


def test_proxy_empty_path_returns_403(client):
    """Empty path parameter returns 403."""
    response = client.get("/proxy?path=")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Group 3: SSRF prevention — allowlist regex tests (EPIC-04)
# ---------------------------------------------------------------------------


def test_proxy_path_traversal_returns_403(client):
    """Path traversal attempt ../../etc/passwd returns 403."""
    response = client.get("/proxy?path=../../etc/passwd")
    assert response.status_code == 403


def test_proxy_absolute_url_returns_403(client):
    """Absolute URL path returns 403 (SSRF via URL scheme)."""
    response = client.get("/proxy?path=http://evil.com/image.jpg")
    assert response.status_code == 403


def test_proxy_wrong_prefix_returns_403(client):
    """Non-Jellyfin prefix path returns 403."""
    response = client.get("/proxy?path=tmdb/abc123/Primary")
    assert response.status_code == 403


def test_proxy_missing_primary_suffix_returns_403(client):
    """Path without /Primary suffix returns 403."""
    response = client.get(f"/proxy?path=jellyfin/{VALID_HEX32}")
    assert response.status_code == 403


def test_proxy_short_id_returns_403(client):
    """Path with too-short ID returns 403."""
    response = client.get("/proxy?path=jellyfin/abc/Primary")
    assert response.status_code == 403


def test_proxy_invalid_chars_in_id_returns_403(client):
    """Path with non-hex characters in ID returns 403."""
    response = client.get(
        "/proxy?path=jellyfin/g1h2i3j4k5l6g1h2i3j4k5l6g1h2i3j4/Primary"
    )
    assert response.status_code == 403


def test_proxy_extra_path_segments_returns_403(client):
    """Path with extra segments after Primary returns 403."""
    response = client.get(f"/proxy?path=jellyfin/{VALID_HEX32}/Primary/extra")
    assert response.status_code == 403


def test_proxy_encoded_path_traversal_returns_403(client):
    """URL-encoded path traversal attempt returns 403."""
    response = client.get("/proxy?path=jellyfin/..%2F..%2Fetc/Primary")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Group 4: Server configuration tests
# ---------------------------------------------------------------------------


def test_proxy_no_jellyfin_url_returns_503(client, monkeypatch):
    """Empty JELLYFIN_URL config returns 503."""
    monkeypatch.setattr(jellyswipe.config, "JELLYFIN_URL", "")
    response = client.get(f"/proxy?path=jellyfin/{VALID_HEX32}/Primary")
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Group 5: Provider error handling tests
# ---------------------------------------------------------------------------


def test_proxy_provider_permission_error_returns_403(client, monkeypatch):
    """Provider PermissionError returns 403."""
    fake = jellyswipe._provider_singleton
    monkeypatch.setattr(
        fake,
        "fetch_library_image",
        MagicMock(side_effect=PermissionError("forbidden")),
    )
    response = client.get(f"/proxy?path=jellyfin/{VALID_HEX32}/Primary")
    assert response.status_code == 403
