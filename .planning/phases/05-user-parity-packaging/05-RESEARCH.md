# Phase 5 research: User parity & packaging

**Date:** 2026-04-23
**Question:** What must be implemented for JUSR-01..04 with minimal churn?

## Findings

- Current data model already partitions by `plex_id`; no schema rename needed for v1. Store Jellyfin user IDs in the same column and document semantics.
- Frontend currently sends `X-Plex-User-ID` and `X-Plex-Token`; this can remain if server treats it as provider identity in Jellyfin mode and optionally accepts neutral aliases.
- Jellyfin user-session flow can use `/Users/AuthenticateByName` (user creds) and user token for user-scoped actions.
- Jellyfin list parity can map to favorites endpoint (`/Users/{userId}/FavoriteItems/{itemId}`) with user token.

## Validation Architecture

- Verify identity partitioning by running two browser sessions with different Jellyfin users and asserting `matches`/`history` do not overlap.
- Verify watchlist/list add with valid/invalid Jellyfin user token.
- Verify frontend header contract by checking requests include provider identity header and not Plex-only semantics in Jellyfin mode.
- Verify packaging by running `python -m py_compile`, `pip install -r requirements.txt`, and `docker build .`.

## Risk notes

- Never leak user token in errors; normalize to generic auth failures.
- Keep Plex flow unchanged to avoid regression.

## RESEARCH COMPLETE
