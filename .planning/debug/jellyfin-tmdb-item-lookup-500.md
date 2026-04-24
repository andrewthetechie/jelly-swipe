---
status: resolved
updated: "2026-04-24T16:31:32Z"
---

# Debug: Jellyfin trailer/cast lookup returns HTTP 500

## Symptoms (from UAT)

- `GET /cast/<jellyfin_item_id>` returns 500.
- `GET /get-trailer/<jellyfin_item_id>` returns 500.
- UI shows trailer "not found" and no cast details.

## Root cause hypothesis

`resolve_item_for_tmdb()` currently performs a single Jellyfin item fetch path:

- `GET /Items/{movie_id}`

For this server profile, deck ids are valid for poster/deck flows but this item lookup path can fail, causing route exceptions to bubble as generic 500s in both trailer/cast routes.

## Fix direction

1. In `media_provider/jellyfin_library.py`, add fallback lookup:
   - Primary: `/Items/{id}`
   - Fallback: `/Users/{userId}/Items/{id}` (or equivalent user-scoped item endpoint for current auth mode)
2. In `app.py` trailer/cast routes, map known lookup misses to controlled user-facing responses (not found / lookup failed) instead of opaque 500.
3. Re-test trailer/cast from a Jellyfin-backed card id that previously failed.

## Resolution

- Added fallback item lookup in `resolve_item_for_tmdb()` from `/Items/{id}` to `/Users/{userId}/Items/{id}`.
- Added controlled 404 mapping for known Jellyfin lookup failures in `/get-trailer` and `/cast`.
- `python -m py_compile media_provider/jellyfin_library.py app.py` passes.
