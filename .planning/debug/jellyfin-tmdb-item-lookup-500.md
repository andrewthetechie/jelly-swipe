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
