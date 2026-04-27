"""
SSRF protection for JELLYFIN_URL — boot-time validation.

Validates URL scheme (http/https only), resolves hostname to IP, and rejects
private/loopback/metadata IP ranges. Operators can bypass with ALLOW_PRIVATE_JELLYFIN=1
for self-hosted setups that legitimately use local addresses.

Uses stdlib only: ipaddress, socket, urllib.parse.

Requirements: SSRF-01, SSRF-02, SSRF-03
"""

import ipaddress
import logging
import os
import socket
import urllib.parse

logger = logging.getLogger(__name__)

# Blocked IP ranges (D-02)
_BLOCKED_IPV4_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("10.0.0.0/8"),         # private Class A
    ipaddress.ip_network("172.16.0.0/12"),      # private Class B
    ipaddress.ip_network("192.168.0.0/16"),     # private Class C
    ipaddress.ip_network("169.254.169.254/32"), # cloud metadata service
]

_BLOCKED_IPV6_RANGES = [
    ipaddress.ip_network("::1/128"),   # loopback
    ipaddress.ip_network("fc00::/7"),  # unique local addresses
    ipaddress.ip_network("fe80::/10"), # link-local addresses
]


def validate_jellyfin_url(url: str) -> None:
    """Validate JELLYFIN_URL for SSRF safety.

    Checks URL scheme (http/https only), resolves hostname to IP,
    and rejects private/loopback/metadata IP ranges.
    Skips all checks when ALLOW_PRIVATE_JELLYFIN=1.

    Raises:
        RuntimeError: If URL scheme is invalid, hostname unresolvable,
                      or IP is in a private range.
    """
    # Step 1 — Override check (D-09)
    if os.getenv("ALLOW_PRIVATE_JELLYFIN") == "1":
        logger.info("SSRF validation bypassed: ALLOW_PRIVATE_JELLYFIN=1")
        return

    # Step 2 — Scheme validation (SSRF-01, D-01)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise RuntimeError(
            f"JELLYFIN_URL has invalid scheme '{parsed.scheme}': "
            f"only http and https are allowed"
        )

    # Step 3 — Extract hostname
    hostname = parsed.hostname
    if not hostname:
        raise RuntimeError(f"JELLYFIN_URL has no hostname: {url}")

    # Step 4 — Resolve to IP (SSRF-03, D-04, D-05)
    try:
        resolved_ip = ipaddress.ip_address(hostname)
    except ValueError:
        # Not an IP literal — resolve via DNS
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            resolved_ip = ipaddress.ip_address(addr_info[0][4][0])
        except socket.gaierror as e:
            raise RuntimeError(
                f"JELLYFIN_URL hostname '{hostname}' could not be resolved: {e}"
            ) from e

    # Step 5 — Private range check (SSRF-02, D-02, D-10)
    for network in _BLOCKED_IPV4_RANGES:
        if resolved_ip in network:
            raise RuntimeError(
                f"JELLYFIN_URL resolves to private IP {resolved_ip} "
                f"(hostname: {hostname}): set ALLOW_PRIVATE_JELLYFIN=1 "
                f"to allow private addresses"
            )

    for network in _BLOCKED_IPV6_RANGES:
        if resolved_ip in network:
            raise RuntimeError(
                f"JELLYFIN_URL resolves to private IP {resolved_ip} "
                f"(hostname: {hostname}): set ALLOW_PRIVATE_JELLYFIN=1 "
                f"to allow private addresses"
            )

    # Step 6 — Log success
    logger.info(f"JELLYFIN_URL validated: {hostname} resolves to {resolved_ip}")
