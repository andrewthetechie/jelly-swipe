---
status: resolved
updated: "2026-04-23T20:11:16Z"
---

# Debug: Jellyfin poster `/proxy` 403 + broken room UI

## Symptoms (from UAT)

- Browser shows broken poster images.
- Server logs show repeated: `GET /proxy?path=jellyfin/<32-hex>/Primary HTTP/1.1" 403`
- Console mentions ServiceWorker intercept for `/room/stream` (may be secondary noise; posters fail independently).

## Root cause (code)

Jellyfin item IDs in this deployment are **32 hex characters without hyphens**, but the allowlist regex only accepts **UUID-with-hyphens (36 chars)**:

- `app.py` `proxy()` for `MEDIA_PROVIDER == "jellyfin"` rejects paths unless:
  - `^jellyfin/[0-9a-fA-F-]{36}/Primary$`
- `media_provider/jellyfin_library.py` `_JF_IMAGE_PATH` matches the same `{36}` constraint.

Thumb URLs are generated as:

- `thumb`: `/proxy?path=jellyfin/{ItemId}/Primary` where `ItemId` is whatever Jellyfin returns.

When `ItemId` is 32-hex, both the Flask gate and provider parser reject/403 before a successful upstream image fetch.

## Fix direction

Align allowlist + parsing with real Jellyfin IDs:

- Accept **either** `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` **or** canonical UUID `8-4-4-4-12`.
- Keep the suffix fixed to `/Primary` and the `jellyfin/` prefix.

## Files involved

- `app.py` — `/proxy` allowlist regex for Jellyfin paths
- `media_provider/jellyfin_library.py` — `_JF_IMAGE_PATH` + `fetch_library_image`
