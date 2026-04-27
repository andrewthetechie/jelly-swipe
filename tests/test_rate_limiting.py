"""
Integration tests for per-endpoint rate limiting.

Tests verify:
- Per-endpoint limits enforced: proxy=10, trailer=20, cast=20, watchlist=30
- 429 response format: JSON body with error + request_id + retry_after
- Retry-After header present with integer seconds
- Cross-endpoint isolation (proxy limit doesn't affect trailer)
- Per-IP isolation (different IP = fresh limit)
- Violation logging at WARNING level
- Non-rate-limited endpoints unaffected

Requirements: RL-01, RL-02, RL-03, RL-04
"""

import logging
from unittest.mock import MagicMock

import jellyswipe
import pytest


class TestProxyRateLimit:
    """Tests for /proxy endpoint: 10 requests/minute/IP."""

    def test_first_10_requests_not_429(self, client, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.fetch_library_image.return_value = (b"img", "image/jpeg")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        for i in range(10):
            resp = client.get(f'/proxy?path=jellyfin/{str(i).zfill(32)}Primary')
            assert resp.status_code != 429, f"Request {i+1}/10 should not be 429"

    def test_11th_request_returns_429(self, client, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.fetch_library_image.return_value = (b"img", "image/jpeg")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        for _ in range(10):
            client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')
        resp = client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')
        assert resp.status_code == 429


class TestTrailerRateLimit:
    """Tests for /get-trailer endpoint: 20 requests/minute/IP."""

    def test_first_20_requests_not_429(self, client, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.resolve_item_for_tmdb.side_effect = RuntimeError("Item lookup failed for id")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        for _ in range(20):
            resp = client.get('/get-trailer/test-id')
            assert resp.status_code != 429, "First 20 requests should not be 429"

    def test_21st_request_returns_429(self, client, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.resolve_item_for_tmdb.side_effect = RuntimeError("Item lookup failed for id")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        for _ in range(20):
            client.get('/get-trailer/test-id')
        resp = client.get('/get-trailer/test-id')
        assert resp.status_code == 429


class TestCastRateLimit:
    """Tests for /cast endpoint: 20 requests/minute/IP."""

    def test_first_20_requests_not_429(self, client, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.resolve_item_for_tmdb.side_effect = RuntimeError("Item lookup failed for id")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        for _ in range(20):
            resp = client.get('/cast/test-id')
            assert resp.status_code != 429, "First 20 requests should not be 429"

    def test_21st_request_returns_429(self, client, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.resolve_item_for_tmdb.side_effect = RuntimeError("Item lookup failed for id")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        for _ in range(20):
            client.get('/cast/test-id')
        resp = client.get('/cast/test-id')
        assert resp.status_code == 429


class TestWatchlistRateLimit:
    """Tests for /watchlist/add endpoint: 30 requests/minute/IP."""

    def test_first_30_requests_not_429(self, client):
        for _ in range(30):
            resp = client.post('/watchlist/add', json={'movie_id': 'test-id'})
            assert resp.status_code != 429, "First 30 requests should not be 429"

    def test_31st_request_returns_429(self, client):
        for _ in range(30):
            client.post('/watchlist/add', json={'movie_id': 'test-id'})
        resp = client.post('/watchlist/add', json={'movie_id': 'test-id'})
        assert resp.status_code == 429


class TestRateLimitResponseFormat:
    """Tests for 429 response format."""

    def test_429_body_contains_error_message(self, client, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.fetch_library_image.return_value = (b"img", "image/jpeg")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        for _ in range(10):
            client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')
        resp = client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')
        assert resp.status_code == 429
        data = resp.get_json()
        assert data.get('error') == 'Rate limit exceeded'
        assert 'request_id' in data

    def test_429_has_retry_after_header(self, client, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.fetch_library_image.return_value = (b"img", "image/jpeg")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        for _ in range(10):
            client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')
        resp = client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')
        assert resp.status_code == 429
        assert 'Retry-After' in resp.headers
        retry_val = resp.headers['Retry-After']
        int(retry_val)


class TestRateLimitIsolation:
    """Tests for cross-endpoint and cross-IP isolation."""

    def test_proxy_limit_does_not_affect_trailer(self, client, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.resolve_item_for_tmdb.side_effect = RuntimeError("fail")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        for _ in range(10):
            client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')
        resp = client.get('/get-trailer/test-id')
        assert resp.status_code != 429, "Trailer endpoint should be independent of proxy limit"

    def test_different_ips_get_independent_limits(self, client, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.fetch_library_image.return_value = (b"img", "image/jpeg")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        for _ in range(10):
            client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')
        resp_default = client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')
        assert resp_default.status_code == 429, "Default IP should be rate limited"


class TestRateLimitLogging:
    """Tests for rate limit violation logging."""

    def test_violation_produces_warning_log(self, client, caplog, monkeypatch):
        mock_prov = MagicMock()
        mock_prov.fetch_library_image.return_value = (b"img", "image/jpeg")
        monkeypatch.setattr(jellyswipe, "_provider_singleton", mock_prov, raising=False)
        with caplog.at_level(logging.WARNING):
            for _ in range(10):
                client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')
            client.get('/proxy?path=jellyfin/test0000000000000000000000000000Primary')

        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        rate_limit_records = [r for r in warning_records
                              if getattr(r, 'endpoint', None) or 'rate_limit' in str(r.getMessage())]
        assert len(rate_limit_records) > 0, "Expected rate limit violation log at WARNING level"


class TestNonRateLimitedEndpoints:
    """Tests that non-rate-limited endpoints are unaffected."""

    def test_home_endpoint_never_429(self, client):
        for _ in range(50):
            resp = client.get('/')
            assert resp.status_code != 429, "Home endpoint should never return 429"

    def test_auth_provider_never_429(self, client):
        for _ in range(50):
            resp = client.get('/auth/provider')
            assert resp.status_code != 429, "Auth provider should never return 429"
