# Stack Research

**Domain:** Jellyfin integration in Python Flask app  
**Researched:** 2026-04-22  
**Confidence:** MEDIUM (verify against your Jellyfin server version)

## Recommended Stack

### Core technologies

| Technology | Version | Purpose | Why recommended |
|------------|---------|---------|------------------|
| Python | 3.11 (existing) | Server | Matches `Dockerfile`. |
| `requests` | Existing | HTTP to Jellyfin REST | Already used for Plex.tv/TMDB; fine for Jellyfin JSON APIs. |
| `jellyfin-apiclient-python` | Latest compatible on PyPI | Optional wrapper | Official-ish community client; can reduce boilerplate for auth and `/Items` queries — **or** use raw `requests` for fewer deps; decide in plan phase after spike. |

### Supporting approach

| Approach | Purpose | When to use |
|----------|---------|-------------|
| Raw REST + small helper module | Full control, minimal dependencies | If client library version pinning is painful. |
| `jellyfin-apiclient-python` | Session/auth helpers | If it cleanly supports your auth method (password vs API key). |

### Auth header (current direction)

Jellyfin expects a **`MediaBrowser`-style `Authorization` header** with Client, Device, DeviceId, Version, and Token fields. Legacy `X-Emby-Token` / `X-MediaBrowser-Token` exist but may be disabled (`EnableLegacyAuthorization`). Prefer the modern header and test on the target server.

**Reference:** [Jellyfin API docs](https://api.jellyfin.org/) and server admin docs for your installed version (auth details evolve by release).

## Installation notes

- Add any new dependency to `requirements.txt` with a version floor if using the Python API client.  
- Docker image must still build without Plex-only env when `MEDIA_PROVIDER=jellyfin`.

## What not to use

- **ApiKey query string alone** as the primary pattern — discouraged for logs and referrer leakage; prefer headers.

---
*Stack research for Jellyfin milestone*
