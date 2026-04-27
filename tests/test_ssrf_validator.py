"""
SSRF validator unit tests.

Tests verify:
- Scheme validation: only http/https allowed
- IPv4 private range rejection (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.169.254)
- IPv6 private range rejection (::1, fc00::/7, fe80::/10)
- Hostname resolution and post-resolution validation
- ALLOW_PRIVATE_JELLYFIN=1 override behavior
- DNS resolution failure handling

Requirements: SSRF-01, SSRF-02, SSRF-03, SSRF-04
"""

import os
import socket
from unittest.mock import patch, MagicMock

import pytest

# Import at module level so jellyswipe.__init__.py loads with ALLOW_PRIVATE_JELLYFIN=1
# (set by conftest.py). This avoids boot-time SSRF validation failures during import.
from jellyswipe.ssrf_validator import validate_jellyfin_url


class TestValidateJellyfinUrl:
    """Unit tests for validate_jellyfin_url function."""

    # Helper: patch DNS then delete override. Order matters because
    # test_rate_limiting.py removes jellyswipe from sys.modules, so
    # patch() may trigger a re-import of __init__.py which calls
    # validate_jellyfin_url at boot. The override must be present
    # during that re-import but absent when the test calls the function.

    # --- Scheme validation (SSRF-01) ---

    def test_rejects_ftp_scheme(self, monkeypatch):
        """FTP scheme is rejected — only http and https are allowed."""
        monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
        with pytest.raises(RuntimeError, match="scheme"):
            validate_jellyfin_url("ftp://evil.com")

    def test_rejects_file_scheme(self, monkeypatch):
        """file:// scheme is rejected — prevents local file access."""
        monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
        with pytest.raises(RuntimeError, match="scheme"):
            validate_jellyfin_url("file:///etc/passwd")

    def test_accepts_http_scheme(self, monkeypatch):
        """HTTP scheme with public IP is accepted."""
        with patch("jellyswipe.ssrf_validator.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ]
            monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
            validate_jellyfin_url("http://public.example.com")

    def test_accepts_https_scheme(self, monkeypatch):
        """HTTPS scheme with public IP is accepted."""
        with patch("jellyswipe.ssrf_validator.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ]
            monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
            validate_jellyfin_url("https://public.example.com")

    # --- IPv4 private ranges (SSRF-02) ---

    def test_rejects_ipv4_loopback(self, monkeypatch):
        """127.0.0.0/8 loopback range is rejected."""
        monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
        with pytest.raises(RuntimeError):
            validate_jellyfin_url("http://127.0.0.1:8096")

    def test_rejects_ipv4_10_range(self, monkeypatch):
        """10.0.0.0/8 private Class A range is rejected."""
        monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
        with pytest.raises(RuntimeError):
            validate_jellyfin_url("http://10.0.0.1:8096")

    def test_rejects_ipv4_172_range(self, monkeypatch):
        """172.16.0.0/12 private Class B range is rejected."""
        monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
        with pytest.raises(RuntimeError):
            validate_jellyfin_url("http://172.16.0.1:8096")

    def test_rejects_ipv4_192_range(self, monkeypatch):
        """192.168.0.0/16 private Class C range is rejected."""
        monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
        with pytest.raises(RuntimeError):
            validate_jellyfin_url("http://192.168.1.1:8096")

    def test_rejects_cloud_metadata(self, monkeypatch):
        """169.254.169.254 cloud metadata endpoint is rejected — prevents credential leakage."""
        monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
        with pytest.raises(RuntimeError):
            validate_jellyfin_url("http://169.254.169.254/latest/meta-data/")

    # --- IPv6 private ranges (SSRF-02) ---

    def test_rejects_ipv6_loopback(self, monkeypatch):
        """::1 IPv6 loopback is rejected."""
        monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
        with pytest.raises(RuntimeError):
            validate_jellyfin_url("http://[::1]:8096")

    # --- Hostname resolution (SSRF-03) ---

    def test_rejects_localhost_hostname(self, monkeypatch):
        """Hostname 'localhost' resolves to 127.0.0.1 and is rejected."""
        with patch("jellyswipe.ssrf_validator.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))
            ]
            monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
            with pytest.raises(RuntimeError):
                validate_jellyfin_url("http://localhost:8096")

    def test_rejects_dns_failure(self, monkeypatch):
        """DNS resolution failure raises RuntimeError with hostname and error details."""
        with patch("jellyswipe.ssrf_validator.socket.getaddrinfo") as mock_dns:
            mock_dns.side_effect = socket.gaierror("Name or service not known")
            monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
            with pytest.raises(RuntimeError, match="nonexistent.invalid"):
                validate_jellyfin_url("http://nonexistent.invalid")

    def test_resolves_hostname_before_check(self, monkeypatch):
        """Hostname resolving to private IP is rejected after DNS resolution."""
        with patch("jellyswipe.ssrf_validator.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0))
            ]
            monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
            with pytest.raises(RuntimeError):
                validate_jellyfin_url("http://myserver.local")

    # --- Override behavior (SSRF-02) ---

    def test_allows_private_when_override_set(self, monkeypatch):
        """ALLOW_PRIVATE_JELLYFIN=1 allows private IPv4 ranges."""
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        validate_jellyfin_url("http://192.168.1.1:8096")

    def test_allows_loopback_when_override_set(self, monkeypatch):
        """ALLOW_PRIVATE_JELLYFIN=1 allows loopback addresses."""
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        validate_jellyfin_url("http://127.0.0.1:8096")

    def test_allows_metadata_when_override_set(self, monkeypatch):
        """ALLOW_PRIVATE_JELLYFIN=1 allows cloud metadata IP."""
        monkeypatch.setenv("ALLOW_PRIVATE_JELLYFIN", "1")
        validate_jellyfin_url("http://169.254.169.254")

    # --- Public URL acceptance ---

    def test_allows_public_url(self, monkeypatch):
        """Public URL with valid DNS resolution is accepted without error."""
        with patch("jellyswipe.ssrf_validator.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ]
            monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
            validate_jellyfin_url("http://jellyfin.example.com:8096")

    # --- Edge cases ---

    def test_rejects_url_without_hostname(self, monkeypatch):
        """URL without a hostname is rejected with RuntimeError."""
        monkeypatch.delenv("ALLOW_PRIVATE_JELLYFIN", raising=False)
        with pytest.raises(RuntimeError):
            validate_jellyfin_url("http://")
